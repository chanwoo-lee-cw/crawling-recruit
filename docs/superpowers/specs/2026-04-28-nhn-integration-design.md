# NHN 채용공고 통합 설계

**날짜**: 2026-04-28  
**범위**: DB BigInteger 마이그레이션 + NHN 공고/지원현황/상세정보 동기화

---

## 1. 배경 및 목표

NHN 그룹(NHN, NHN Cloud, NHN Dooray 등)은 자체 채용 사이트(`careers.nhn.com`)를 운영한다. 기존 Wanted, Remember와 동일한 패턴으로 NHN 공고를 DB에 동기화하여 미지원 공고 탐색 대상에 포함시키는 것이 목표다.

NHN 공고 ID는 int64 형식(`"4317632272881051418"`)으로 현재 DB의 `INT` 컬럼에 저장 불가하므로, DB 마이그레이션이 선행된다.

---

## 2. 아키텍처 개요

기존 Wanted/Remember 패턴을 그대로 따른다. 각 소스는 `services/{source}/` 디렉토리에 client, syncer, application_syncer, detail_syncer를 가진다.

### 신규 파일

```
services/nhn/
  __init__.py
  nhn_constants.py
  nhn_client.py
  nhn_syncer.py
  nhn_application_syncer.py
  nhn_detail_syncer.py

tools/
  nhn_sync_jobs.py
```

### 수정 파일

```
db/models/job.py                  # platform_id: Integer → BigInteger
db/models/application.py          # platform_id: Integer → BigInteger
db/connection.py                  # migrate_bigint() 추가
tools/migrate_db.py               # BigInteger 마이그레이션 체인
tools/sync_applications.py        # NHN case 추가
tools/sync_job_details.py         # source param + NHN 분기
services/wanted/                  # wanted_detail_syncer.py 추가
services/remember/                # remember_detail_syncer.py 추가 (stub)
services/jobs/job_service.py      # NHN 파싱 메서드 추가
main.py                           # nhn_sync_jobs 등록
```

---

## 3. DB 마이그레이션

### 모델 변경

`db/models/job.py`와 `db/models/application.py`의 `platform_id` 컬럼 타입을 `Integer` → `BigInteger`로 변경한다.

```python
from sqlalchemy import BigInteger
platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

### migrate_bigint()

`db/connection.py`에 멱등 마이그레이션 함수 추가:

```python
def migrate_bigint(engine) -> str:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_NAME='jobs' AND COLUMN_NAME='platform_id' AND TABLE_SCHEMA=DATABASE()"
        ))
        row = result.fetchone()
        if row and row[0].lower() == "bigint":
            return "BigInteger 마이그레이션 이미 완료됨"
        conn.execute(text("ALTER TABLE jobs MODIFY platform_id BIGINT NOT NULL"))
        conn.execute(text("ALTER TABLE applications MODIFY platform_id BIGINT NOT NULL"))
        conn.commit()
    return "BigInteger 마이그레이션 완료"
```

`tools/migrate_db.py`에서 기존 `migrate()` 후 `migrate_bigint()`를 체인으로 호출한다.

---

## 4. NHN API

### 엔드포인트

| 용도 | Method | URL |
|------|--------|-----|
| 로그인 | POST | `https://careers.nhn.com/v1/accounts/sign-in` |
| 공고 목록 | GET | `https://careers.nhn.com/v1/job-postings` |
| 지원현황 | GET | `https://careers.nhn.com/v1/applicants/me/job-postings` |
| 공고 상세 | GET | `https://careers.nhn.com/v1/job-postings/{job_id}` |

### 공고 목록 쿼리 파라미터

- `jobGroupId`: 직군 ID (Tech = `"3645799730550663017"`)
- `jobSeriesId`: 직무 ID (선택, e.g. Backend = `"3665304227944319351"`)
- `page`: 0-based 페이지
- `size`: 페이지당 공고 수 (기본 30)

### 인증

로그인 API가 `set-cookie`로 `access_token`(30분)과 `refresh_token`(60분)을 내려준다. `NHNClient` 초기화 시 자동 로그인하여 쿠키를 인스턴스에 보관한다. 지원현황, 상세정보 API 호출 시 쿠키를 자동 포함한다.

`.env` 필요 키:
```
NHN_EMAIL=...
NHN_PASSWORD=...
```

---

## 5. NHN 클라이언트 (`nhn_client.py`)

```python
class NHNClient:
    def __init__(self):
        self._email = os.getenv("NHN_EMAIL")
        self._password = os.getenv("NHN_PASSWORD")
        self._cookies: dict = {}
        self._login()

    def _login(self): ...          # POST sign-in → cookies 저장
    def fetch_jobs(...): ...       # GET job-postings, 페이지네이션
    def fetch_applications(): ...  # GET applicants/me/job-postings
    def fetch_job_detail(job_id: str): ...  # GET job-postings/{id}
```

`fetch_jobs()`는 `page` 증가로 페이지네이션. `result`가 빈 배열이거나 `limit_pages` 도달 시 중단.

---

## 6. 파싱 로직 (`job_service.py`)

### `_parse_nhn_job(raw)`

| NHN 응답 필드 | Job 모델 필드 |
|---|---|
| `int(raw["id"])` | `platform_id` |
| `int(raw["corporation"]["id"])` | `company_id` |
| `raw["corporation"]["name"]` | `company_name` |
| `raw["name"]` | `title` |
| `raw["employeeType"]["name"]` via `EMPLOYMENT_TYPE_MAP` | `employment_type` |
| `None` | `location` (목록/상세 모두 위치 정보 없음) |
| `None` | `job_group_id`, `category_tag_id` |

### `_parse_nhn_applications(raw_apps)`

```
jobPostingId  → job_platform_id: int(raw["jobPostingId"])
applicationId → platform_id:     int(raw["applicationId"])
displayStepButtonCd → status
finalSubmitDatetime → apply_time_str
```

`finalSubmitYn == "N"` (미완료 지원)은 skip한다.

### `_parse_nhn_detail(raw_detail)` (NHNDetailSyncer 내부)

`jobPostingContentsItems` 섹션 제목으로 필드 추출:

| 섹션 title 포함 키워드 | 추출 필드 |
|---|---|
| `"자격요건"` | `requirements` (contents 리스트 `"\n".join`) |
| `"우대사항"` | `preferred_points` |

`skill_tags`: `jobSeries[].name` → `[{"text": "Backend"}, ...]`

---

## 7. Detail Syncer 패턴

`sync_job_details.py`를 `sync_applications.py`와 동일한 dispatcher 패턴으로 전환한다.

### 각 syncer

- **`services/wanted/wanted_detail_syncer.py`**: 기존 `sync_job_details.py` 로직 그대로 이동
- **`services/remember/remember_detail_syncer.py`**: stub — `"Remember 상세 동기화는 지원하지 않습니다."` 반환
- **`services/nhn/nhn_detail_syncer.py`**: NHN 상세 API 호출 → `jobPostingContentsItems` 파싱 → `upsert_job_details`

### `tools/sync_job_details.py` (수정 후)

```python
def sync_job_details(source: str = WANTED, job_ids=None, limit=None) -> str:
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
```

### `JobService.get_jobs_without_details()` 수정

`source` 파라미터 추가 — NHN 공고도 조회 가능하게 한다.

---

## 8. 신규 MCP 툴 (`tools/nhn_sync_jobs.py`)

```python
def nhn_sync_jobs(
    job_group_id: str = NHNClientConst.TECH_GROUP_ID,
    job_series_ids: list[str] | None = None,
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """NHN 채용공고를 동기화한다."""
    service = JobService(get_engine())
    preset = service.get_preset_params(NHN)
    if preset:
        p = preset.params
        job_group_id = p.get("job_group_id", job_group_id)
        job_series_ids = p.get("job_series_ids", job_series_ids)
        limit_pages = p.get("limit_pages", limit_pages)
    return NHNSyncer(service).sync(
        job_group_id=job_group_id,
        job_series_ids=job_series_ids,
        limit_pages=limit_pages,
    )
```

`main.py`에 `mcp.tool()(nhn_sync_jobs)` 추가.

---

## 9. 상수 (`nhn_constants.py`)

```python
NHN = "nhn"
NHN_JOB_BASE_URL = "https://careers.nhn.com/job-postings"

class NHNClientConst:
    LOGIN_URL = "https://careers.nhn.com/v1/accounts/sign-in"
    JOBS_URL = "https://careers.nhn.com/v1/job-postings"
    APPLICATIONS_URL = "https://careers.nhn.com/v1/applicants/me/job-postings"
    DETAIL_URL = "https://careers.nhn.com/v1/job-postings/{job_id}"
    TECH_GROUP_ID = "3645799730550663017"
```

`job_service.py`의 `JOB_BASE_URLS`에 `NHN: NHN_JOB_BASE_URL` 추가.

---

## 10. 테스트 전략

- 기존 Wanted/Remember 테스트는 영향 없음 (BigInteger는 하위 호환)
- `test_tools.py` 또는 신규 `test_nhn.py`에 NHN 파싱 유닛 테스트 추가:
  - `_parse_nhn_job()` — platform_id int 변환, employment_type 매핑
  - `_parse_nhn_applications()` — finalSubmitYn=N skip 검증
  - `_parse_nhn_detail()` — 섹션 타이틀 매핑 검증
- API 호출 테스트는 mocking 없이 실제 호출로만 검증 (기존 프로젝트 방침)
