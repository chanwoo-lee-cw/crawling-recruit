# 프로젝트 개요
Claude Code, Superpowers을 사용해 현재 지원 안 한 채용공고를 찾아주는 MCP 서버 프로젝트.
MCP 서버는 데이터·도구 제공만 담당하고, 추론(추천)은 MCP 클라이언트(Claude Code)가 직접 수행한다.

# 기술 스택
- Python 3.11
- MySQL
- FastMCP (MCP 서버 프레임워크)
- SQLAlchemy 2.x (DB ORM)
- httpx (Wanted API 호출)

# 파일 구조

```
main.py                        # FastMCP 서버 진입점, 툴 등록
services/
  job_service.py               # DB CRUD, skill 매칭 로직 (JobService)
  wanted_client.py             # Wanted API 클라이언트
db/
  connection.py                # DB 엔진 생성, 테이블 초기화
  models.py                    # SQLAlchemy 테이블 정의
tools/
  sync_jobs.py                 # 채용공고 동기화 (Wanted API → DB)
  sync_applications.py         # 지원현황 동기화
  sync_job_details.py          # 공고 상세정보 수집 (requirements, skill_tags 등)
  get_unapplied_jobs.py        # 미지원 공고 목록 조회 (마크다운 테이블)
  get_job_candidates.py        # skill 매칭 후보 공고 JSON 반환 (Claude Code가 추천 담당)
  save_search_preset.py        # 검색 프리셋 저장
  list_search_presets.py       # 저장된 프리셋 목록 조회
  debug_applications.py        # 지원현황 디버그용
tests/
  test_job_service.py
  test_tools.py
  test_db.py
  test_wanted_client.py
docs/superpowers/
  plans/                       # 구현 계획 문서
  specs/                       # 설계 스펙 문서
doc/
  db.md                        # DB 스키마 문서
  wanted.md                    # Wanted API 문서
```

# 테스트 실행
```bash
pytest
```

# 코드 규칙
- NEVER : 쿠키나 계정 정보는 .env에 저장하고 커밋을 금지한다.
- MCP 서버 툴은 데이터 제공만 담당. 추론/추천 로직은 툴 내부에 넣지 않는다.
- 빈 결과·에러는 한국어 문자열로 반환한다 (다른 툴과 동일한 패턴 유지).
- employment_type 한국어↔영어 변환은 `JobService.EMPLOYMENT_TYPE_MAP`이 처리.

# 주의사항
- `anthropic` 패키지는 requirements.txt에 남아 있지만 현재 툴에서는 사용하지 않음 (추후 제거 가능).
- `get_job_candidates`는 `fetched_at IS NULL`인 공고(상세 미수집)를 자동 제외하므로, 먼저 `sync_job_details`를 실행해야 추천 후보가 나온다.
