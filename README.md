# 리눅스 코레일 빈좌석 알림

Python 3.9 이상. 서울→강릉, 2026-11-07 08:57/09:55, 성인 2명, 일반실 기본 설정.
실제 시간표가 해당 시각과 다르면 조회되지 않으므로 코레일톡 시간표와 대조하세요.

## 설치 및 실행

압축을 풀고 해당 디렉터리에서 실행합니다. Ubuntu에서 venv가 없으면 `sudo apt install python3-venv`로 설치합니다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
nano .env
.venv/bin/python alert.py --test-notify
.venv/bin/python alert.py --once
.venv/bin/python alert.py
```

`.env`의 코레일 회원번호·비밀번호와 텔레그램 설정을 본인 값으로 수정하세요. 비밀번호는 채팅에 보내지 마세요.
텔레그램에서 공식 @BotFather의 `/newbot`으로 봇과 토큰을 만든 뒤 새 봇에 `/start`를 보냅니다.
본인 기기에서 `https://api.telegram.org/bot<토큰>/getUpdates`를 열어 본인 메시지의 `message.chat.id`를 확인합니다.
토큰을 포함한 주소를 공유하지 마세요. 그룹이 아닌 본인 개인 채팅 ID를 사용하세요.
`--test-notify`는 직접 실행할 때만 시험 메시지를 보냅니다.

## 백그라운드 실행

```bash
nohup .venv/bin/python -u alert.py > alert.log 2>&1 &
echo $! > alert.pid
tail -f alert.log
```

종료: `kill "$(cat alert.pid)"`. 서버를 재부팅하면 수동으로 다시 실행해야 합니다.
이미 실행 중인 프로그램을 중복 실행하지 마세요.

## 설정과 동작

- `SEAT_CLASS`: `general` 일반실, `special` 특실, `any` 둘 중 하나.
- 기본 약 120초마다 확인. 최소 60초. 오류가 반복되면 점차 간격을 늘립니다.
- 같은 출발 시각의 알림은 기본 10분에 한 번. 실패한 전송은 다음 주기에 재시도합니다.
- 세션 만료 시 다음 주기에 재로그인하며 모든 출발 시각이 지나면 종료합니다.
- 알림만 전송합니다. 예약·결제 호출은 없습니다.
- 성인 2명을 조회 조건으로 보내지만 응답의 예약 가능 표시는 잔여 좌석 수나 연석 확보를 보장하지 않습니다.
- 사용한 korail2는 비공식 라이브러리이며, 매크로 방지 인증 대응 PR #54가 적용된 커밋으로 고정되어 있습니다. `X_DYNAPATH_M_TOKEN`을 직접 설정할 필요는 없습니다. 서버 변경·접속 제한·인증 변경 시 작동하지 않을 수 있습니다.
- 계정과 외부 네트워크가 없는 제작 환경에서 실제 로그인·좌석 조회·메시지 전송은 검증하지 않았습니다.
  우선 `--test-notify`, `--once`를 실행하고 로그를 확인하세요. 파일 생성만으로 감시는 시작되지 않습니다.

구현 참고: https://github.com/carpedm20/korail2/pull/54
