# 프로젝트 개요
Claude Code, Superpowers을 사용해 현재 지원 안 한 채용공고를 찾아주는 MCP 서버 프로젝트.
MCP 서버는 데이터·도구 제공만 담당하고, 추론(추천)은 MCP 클라이언트(Claude Code)가 직접 수행한다.

# 기술 스택
- Python 3.11
- MySQL
- FastMCP (MCP 서버 프레임워크)
- SQLAlchemy 2.x (DB ORM)
- httpx (HTTP 클라이언트)
- beautifulsoup4 (HTML 파싱)

# 파일 구조

```
main.py                        # FastMCP 서버 진입점, 툴 등록
constants.py                   # 전역 상수 (CRAWL_DELAY_SECONDS 등)
domain.py                      # 데이터 클래스 (JobDetail 등)
db/
  connection.py                # DB 엔진 생성, 테이블 초기화
  models.py                    # SQLAlchemy 테이블 정의
services/
  base_syncer.py               # 모든 Syncer의 기반 클래스 (BaseSyncer)
  jobs/
    job_service.py             # DB CRUD, upsert, skill 매칭 (JobService)
  wanted/
    wanted_constants.py
    wanted_client.py           # Wanted API 리스트·상세·지원현황
    wanted_syncer.py
    wanted_detail_syncer.py
    wanted_application_syncer.py
  remember/
    remember_constants.py
    remember_client.py
    remember_syncer.py
    remember_detail_syncer.py
    remember_application_syncer.py
  nhn/
    nhn_constants.py
    nhn_client.py
    nhn_syncer.py
    nhn_detail_syncer.py
    nhn_application_syncer.py
  naver/
    naver_constants.py
    naver_client.py            # 리스트 JSON + 상세 HTML 수집
    naver_syncer.py
    naver_detail_syncer.py     # BeautifulSoup HTML 파싱
tools/
  wanted_sync_jobs.py          # 채용공고 동기화 (Wanted)
  remember_sync_jobs.py        # 채용공고 동기화 (Remember)
  nhn_sync_jobs.py             # 채용공고 동기화 (NHN)
  naver_sync_jobs.py           # 채용공고 동기화 (Naver)
  sync_applications.py         # 지원현황 동기화 (source 인자로 분기)
  sync_job_details.py          # 공고 상세정보 수집 (source 인자로 분기)
  get_unapplied_jobs.py        # 미지원 공고 목록 조회 (마크다운 테이블)
  get_job_candidates.py        # skill 매칭 후보 공고 JSON 반환
  save_search_preset.py        # 검색 프리셋 저장
  list_search_presets.py       # 저장된 프리셋 목록 조회
  skip_jobs.py                 # 공고 건너뛰기
  save_job_evaluations.py      # 공고 평가 저장
  migrate_db.py                # DB 마이그레이션
  debug_applications.py        # 지원현황 디버그용
scripts/
  daily_sync.py                # 전체 소스 일괄 동기화 (cron용)
tests/
  test_job_service.py
  test_tools.py
  test_db.py
  test_syncer.py
  test_repositories.py
  test_transaction.py
  test_daily_sync.py
  test_naver_client.py
  test_naver_syncer.py
  test_naver_detail_syncer.py
  test_nhn.py
  wanted/
  remember/
docs/superpowers/
  plans/                       # 구현 계획 문서
  specs/                       # 설계 스펙 문서
doc/
  db.md                        # DB 스키마 문서
  wanted.md                    # Wanted API 문서
```

# 테스트 실행
```bash
.venv/bin/python -m pytest
```

모든 Python 실행은 `.venv/bin/python`을 직접 사용한다. `pytest`, `python` 등 글로벌 명령어를 탐색하지 말 것. `find`로 venv 경로를 찾는 것도 금지.

# 코드 규칙
- NEVER : 쿠키나 계정 정보는 .env에 저장하고 커밋을 금지한다.
- MCP 서버 툴은 데이터 제공만 담당. 추론/추천 로직은 툴 내부에 넣지 않는다.
- 빈 결과·에러는 한국어 문자열로 반환한다 (다른 툴과 동일한 패턴 유지).
- employment_type 한국어↔영어 변환은 `JobService.EMPLOYMENT_TYPE_MAP`이 처리.

# 소스 추가 패턴 (새 채용 플랫폼 연동 시)
각 소스는 `services/<source>/` 패키지로 격리되고 `BaseSyncer`를 구현한다.
1. `<source>_constants.py` — 소스 문자열, URL 상수
2. `<source>_client.py` — HTTP 수집 (리스트·상세·지원현황)
3. `<source>_syncer.py` — 리스트 동기화, `BaseSyncer` 구현
4. `<source>_detail_syncer.py` — 상세 수집, `BaseSyncer` 구현
5. `<source>_application_syncer.py` — 지원현황 동기화 (지원 없으면 한국어 메시지 반환)
6. `job_service.py`에 `_parse_<source>_job()` + `_parse_job()` 분기 추가
7. `tools/<source>_sync_jobs.py` — MCP 툴 진입점
8. `sync_job_details.py`, `sync_applications.py`, `daily_sync.py`, `main.py` 각각에 분기·등록

# 주의사항
- `anthropic` 패키지는 requirements.txt에 남아 있지만 현재 툴에서는 사용하지 않음 (추후 제거 가능).
- `get_job_candidates`는 `fetched_at IS NULL`인 공고(상세 미수집)를 자동 제외하므로, 먼저 `sync_job_details`를 실행해야 추천 후보가 나온다.
- 네이버는 지원현황 API 미지원 — `sync_applications(source="naver")`는 한국어 메시지만 반환.
