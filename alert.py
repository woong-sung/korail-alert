#!/usr/bin/env python3
"""Read-only Korail availability watcher. Python 3.11+."""
import argparse
import datetime as dt
import logging
import os
import random
import signal
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from pykorail import (
    AccessRestrictedError, AdultPassenger, Korail, NeedToLoginError,
    NoResultsError, TrainType,
)

STOP = threading.Event()
LOG = logging.getLogger('korail-alert')
DEVICE_ID_FILE = Path(__file__).with_name('.korail-android-id')


def create_client(korail_id, korail_password):
    android_id = DEVICE_ID_FILE.read_text(encoding='ascii').strip() if DEVICE_ID_FILE.exists() else None
    client = Korail(android_id=android_id)
    if android_id is None:
        DEVICE_ID_FILE.write_text(client.android_id + '\n', encoding='ascii')
        try:
            DEVICE_ID_FILE.chmod(0o600)
        except OSError:
            pass
        LOG.info('새 코레일 기기 ID를 생성해 %s에 저장했습니다.', DEVICE_ID_FILE.name)
    try:
        client.login(korail_id, korail_password)
    except BaseException:
        client.close()
        raise
    return client


def notify(message):
    # Do not log request URLs: they contain the bot token.
    try:
        r = requests.post(
            'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/sendMessage',
            json={'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': message}, timeout=20)
        r.raise_for_status()
        if not r.json().get('ok'):
            raise ValueError('telegram rejected message')
    except Exception:
        raise RuntimeError('텔레그램 전송 실패. 토큰·chat_id·네트워크를 확인하세요.') from None


def main():
    load_dotenv(Path(__file__).with_name('.env'))
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-notify', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for key in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'):
        if not os.getenv(key):
            parser.error(key + ' 설정 필요')
    if args.test_notify:
        notify('코레일 알림 테스트: 텔레그램 연결 성공')
        return
    for key in ('KORAIL_ID', 'KORAIL_PASSWORD'):
        if not os.getenv(key):
            parser.error(key + ' 설정 필요')
    date = os.getenv('TRAVEL_DATE', '20261107')
    times = sorted(set(t.strip().replace(':', '') for t in os.getenv('DEPARTURE_TIMES', '0857,0955').split(',')))
    try:
        day = dt.datetime.strptime(date, '%Y%m%d').date()
        for t in times:
            if len(t) != 4:
                raise ValueError()
            dt.datetime.strptime(t, '%H%M')
        adults = int(os.getenv('ADULTS', '2'))
        interval = max(60, int(os.getenv('INTERVAL_SECONDS', '120')))
        cooldown = max(60, int(os.getenv('ALERT_COOLDOWN_SECONDS', '600')))
        if adults < 1:
            raise ValueError()
    except ValueError:
        parser.error('날짜·시각·인원·주기 설정을 확인하세요.')
    seat_class = os.getenv('SEAT_CLASS', 'general')
    if seat_class not in ('general', 'special', 'any'):
        parser.error('SEAT_CLASS: general / special / any')
    dep, arr = os.getenv('DEPARTURE', '서울'), os.getenv('ARRIVAL', '강릉')
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    client = None
    last_sent = {}
    failures = 0
    while not STOP.is_set():
        now = dt.datetime.now(ZoneInfo('Asia/Seoul'))
        pending = [t for t in times if dt.datetime.combine(day, dt.time(int(t[:2]), int(t[2:])), tzinfo=now.tzinfo) > now]
        if not pending:
            LOG.info('대상 열차 출발 시각이 모두 지나 종료합니다.')
            return
        try:
            if client is None:
                client = create_client(os.environ['KORAIL_ID'], os.environ['KORAIL_PASSWORD'])
            matched = set()
            # Query each exact time separately; search_train returns at most 10 results.
            for target in pending:
                if STOP.is_set():
                    break
                try:
                    depart_after = dt.datetime.combine(
                        day, dt.time(int(target[:2]), int(target[2:])), tzinfo=now.tzinfo)
                    trains = client.trains.search(dep, arr, depart_after=depart_after,
                        train_type=TrainType.KTX, passengers=[AdultPassenger(adults)], include_no_seats=True)
                except NoResultsError:
                    trains = []
                for train in trains:
                    if train.dep_date != date or train.dep_time[:4] != target:
                        continue
                    matched.add(target)
                    general, special = train.has_general_seat(), train.has_special_seat()
                    available = (general if seat_class == 'general' else special if seat_class == 'special' else general or special)
                    if available and time.monotonic() - last_sent.get(target, float('-inf')) >= cooldown:
                        classes = '/'.join(c for c, ok in [('일반실', general), ('특실', special)] if ok)
                        notify(f'[코레일 빈좌석 표시 감지]\n{day} {dep} → {arr}\n출발 {target[:2]}:{target[2:]} / {classes}\n성인 {adults}명 조건 조회\n잔여 수량·연석·예약 성공은 보장되지 않습니다. 코레일톡에서 확인하세요.')
                        last_sent[target] = time.monotonic()
                    LOG.info('%s:%s 일반실=%s 특실=%s', target[:2], target[2:], general, special)
                if target not in matched:
                    LOG.warning('%s 대상 열차가 조회되지 않음 (시간표·조회 가능 기간 확인)', target)
                if len(pending) > 1 and target != pending[-1]:
                    STOP.wait(3)
            failures = 0
        except AccessRestrictedError as exc:
            if client is not None:
                client.close()
            LOG.error('코레일 접근 제한으로 감시를 중단합니다 (%s). 즉시 재시도하지 마세요.', exc)
            return
        except NeedToLoginError:
            if client is not None:
                client.close()
            client = None
            failures += 1
            LOG.warning('세션 만료. 다음 주기에 재로그인합니다.')
        except Exception as exc:
            failures += 1
            if client is not None:
                client.close()
            client = None
            LOG.error('조회/알림 실패 (%s: %s), 연속 %d회. 계정·연결·라이브러리 호환성을 확인하세요.',
                type(exc).__name__, exc, failures)
            if args.once:
                raise SystemExit(1)
        if args.once:
            return
        STOP.wait(min(1800, interval * (2 ** min(failures, 4))) + random.uniform(0, 10))


if __name__ == '__main__':
    main()
