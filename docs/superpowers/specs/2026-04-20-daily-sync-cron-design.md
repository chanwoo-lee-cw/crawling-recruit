# Daily Sync Cron Job 설계

## 개요

매일 오후 10시에 macOS crontab을 통해 전체 크롤링 파이프라인을 자동 실행하는 기능.

- **환경**: 로컬 맥 (crontab)
- **실행 시각**: 매일 22:00
- **파이프라인**: sync_jobs → sync_job_details → sync_applications

## 아키텍처

MCP 서버를 거치지 않고 `tools/*.py` 함수들을 직접 import해서 호출하는 독립 Python 스크립트를 만들고 crontab에 등록한다.

```
scripts/daily_sync.py   # 러너 스크립트
logs/daily_sync.log     # 로그 파일 (append)
```

## 파이프라인 순서

```
sync_jobs(wanted) → sync_jobs(remember) → [추후 소스] → sync_job_details → sync_applications
```

소스 확장은 `SOURCES` 리스트에 항목만 추가하면 된다.

```python
SOURCES = ["wanted", "remember"]  # 추후 사이트 추가 시 여기만 수정
```

## 에러 처리

- 각 단계를 `try/except`로 감싸서 한 단계 실패해도 나머지가 계속 실행
- `sync_jobs`가 모두 실패하면 `sync_job_details`는 스킵
- 모든 결과는 `logs/daily_sync.log`에 append 방식으로 저장

## 로그 포맷

```
[2026-04-20 22:00:01] === daily sync start ===
[2026-04-20 22:00:05] sync_jobs(wanted): 완료 - 공고 42개 동기화
[2026-04-20 22:00:09] sync_jobs(remember): 완료 - 공고 18개 동기화
[2026-04-20 22:01:02] sync_job_details: 완료 - 상세 60개 수집
[2026-04-20 22:01:15] sync_applications: 완료
[2026-04-20 22:01:15] === daily sync end ===
```

## crontab 등록

```
0 22 * * * cd /path/to/project && .venv/bin/python scripts/daily_sync.py >> logs/daily_sync.log 2>&1
```

## 주의사항

- Mac이 22:00에 잠자기 상태이면 실행되지 않음 (launchd와의 차이점)
- `.env` 환경 변수는 스크립트 내에서 `python-dotenv`로 로드
- `logs/` 디렉토리는 `.gitignore`에 추가
