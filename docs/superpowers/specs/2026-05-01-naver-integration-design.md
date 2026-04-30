# 네이버 채용공고 크롤러 설계

**날짜:** 2026-05-01  
**범위:** 네이버 채용 사이트(recruit.navercorp.com) 리스트·상세 수집 → DB 동기화

---

## 1. 목표

네이버 계열사 전체(NAVER, NAVER WEBTOON, NAVER LABS 등)의 채용공고를 기존 Wanted/Remember/NHN과 동일한 패턴으로 수집해 DB에 저장한다. 수집 후 `get_job_candidates` 툴이 네이버 공고도 추천 후보로 반환할 수 있어야 한다.

---

## 2. API 명세

### 2.1 채용공고 리스트

```
GET https://recruit.navercorp.com/rcrt/loadJobList.do
  ?subJobCdArr=&sysCompanyCdArr=&empTypeCdArr=&entTypeCdArr=&workAreaCdArr=&sw=&firstIndex=0
```

- 인증 불필요 (공개 API)
- `firstIndex`: 오프셋 페이지네이션 (0부터 시작, `PAGE_SIZE`씩 증가)
- 응답: `{ "result": "Y", "list": [...], "totalSize": N }`
- `list`가 비거나 `firstIndex >= totalSize`이면 수집 종료
- 첫 페이지 이후 요청마다 `CRAWL_DELAY_SECONDS` 적용

주요 응답 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `annoId` | int | 공고 ID (platform_id로 저장) |
| `sysCompanyCdNm` | str | 회사명 (NAVER, NAVER WEBTOON 등) |
| `annoSubject` | str | 공고 제목 |
| `empTypeCdNm` | str | 고용형태 (정규, 계약, 인턴) |
| `subJobCdNm` | str | 직무 카테고리 |

`annoId`는 API에서 항상 숫자형 integer로 반환된다(예: `30004786`). `platform_id`는 `int(raw["annoId"])`로 저장한다. NHN과 동일하게 필드 부재/타입 오류는 `upsert_jobs`의 호출 스택으로 전파되며 `daily_sync` try/except가 캐치한다.

### 2.2 채용공고 상세

```
GET https://recruit.navercorp.com/rcrt/view.do?annoId={annoId}
```

- HTML 응답, BeautifulSoup으로 파싱
- `div.detail_wrap > div.detail_box` 순회
  - `h4.detail_title` 텍스트에 "자격요건" 포함 → `requirements`
  - `h4.detail_title` 텍스트에 "우대사항" 포함 → `preferred_points`
  - 매칭 없으면 첫 번째 박스 텍스트를 `requirements` fallback
- `fetch_job_detail()`에서 `httpx` 요청은 `try/except Exception`으로 감싸고, 어떠한 예외(연결 오류, 타임아웃, HTTP 오류)도 `None` 반환으로 처리한다.

---

## 3. 파일 구조

### 신규 생성

```
services/naver/
  __init__.py
  naver_constants.py       # NAVER 상수, URL 정의
  naver_client.py          # NaverClient: fetch_jobs(), fetch_job_detail()
  naver_syncer.py          # NaverSyncer(BaseSyncer): 리스트 동기화
  naver_detail_syncer.py   # NaverDetailSyncer(BaseSyncer): HTML 상세 수집

tools/
  naver_sync_jobs.py       # MCP 툴 함수
```

### 기존 수정

| 파일 | 변경 내용 |
|---|---|
| `services/jobs/job_service.py` | `_parse_naver_job()` 추가; `_parse_job()` 디스패처에 `source == NAVER` 분기 추가; `JOB_BASE_URLS`에 NAVER 추가; `build_job_url()` 헬퍼 추출 (아래 참조) |
| `tools/get_job_candidates.py` | line 50의 URL 조합을 `build_job_url(c.source, c.platform_id)` 호출로 변경 |
| `scripts/daily_sync.py` | `SOURCES`에 NAVER 추가; 소스 디스패치 블록에 `elif source == NAVER: naver_sync()` 추가; `naver_sync()` 함수 추가 |
| `tools/sync_job_details.py` | `if source == NAVER` 분기를 기존 fallback(`WantedDetailSyncer`) 전에 추가; docstring 업데이트 |
| `tools/sync_applications.py` | `if source == NAVER` 분기를 기존 fallback(`WantedApplicationSyncer`) 전에 추가 → 한국어 안내 문자열 반환 |
| `main.py` | `naver_sync_jobs` 툴 등록 |
| `requirements.txt` | `beautifulsoup4` 추가 |

---

## 4. 컴포넌트 설계

### 4.1 naver_constants.py

```python
NAVER = "naver"
NAVER_LIST_URL = "https://recruit.navercorp.com/rcrt/loadJobList.do"
NAVER_DETAIL_URL = "https://recruit.navercorp.com/rcrt/view.do"
NAVER_JOB_BASE_URL = "https://recruit.navercorp.com/rcrt/view.do?annoId="
PAGE_SIZE = 20
```

### 4.2 URL 조합 헬퍼 (`job_service.py`에 추가)

기존 URL 조합 로직(`f"{base_url}/{platform_id}"`)은 쿼리스트링 방식인 네이버 URL에서 잘못된 결과를 낸다. `build_job_url()`을 추출해 두 곳(기존 `get_unapplied_jobs` line 308, `get_job_candidates.py` line 50)에서 공통 사용한다.

```python
def build_job_url(source: str, platform_id: int) -> str:
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    if base_url.endswith("="):
        return f"{base_url}{platform_id}"
    return f"{base_url}/{platform_id}"
```

`get_job_candidates.py` 변경:
```python
# 기존
"url": f"{JOB_BASE_URLS.get(c.source, WANTED_JOB_BASE_URL)}/{c.platform_id}",
# 변경
"url": build_job_url(c.source, c.platform_id),
```

`get_unapplied_jobs` 내부 `job_service.py` line 308도 동일하게 교체한다.

### 4.3 NaverClient

```python
class NaverClient:
    PAGE_SIZE = 20

    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        # firstIndex를 PAGE_SIZE씩 증가
        # 첫 페이지 이후 각 요청 전 CRAWL_DELAY_SECONDS 대기
        # list가 비거나 firstIndex >= totalSize이면 종료
        # limit_pages 도달 시 조기 종료

    def fetch_job_detail(self, anno_id: int) -> str | None:
        # try/except Exception으로 감싸서 모든 오류를 None으로 처리
        # 성공 시 HTML 문자열 반환
```

### 4.4 NaverSyncer

```python
class NaverSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        jobs = NaverClient().fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=NAVER, full_sync=limit_pages is None)
```

### 4.5 NaverDetailSyncer

```python
class NaverDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        # get_jobs_without_details(source=NAVER, job_ids=job_ids, limit=limit)
        # 각 공고마다 (첫 공고 제외) CRAWL_DELAY_SECONDS 적용
        # fetch_job_detail() → _parse_naver_detail() → JobDetail 목록 구성
        # upsert_job_details() 호출

    @staticmethod
    def _parse_naver_detail(html: str) -> dict:
        # BeautifulSoup으로 div.detail_box 순회
        # returns: {"requirements": str|None, "preferred_points": str|None, "skill_tags": list[dict]}
        # skill_tags: detail HTML에서 추출 가능 시, 없으면 빈 리스트
```

`sync(job_ids, limit)` 시그니처는 `NHNDetailSyncer`와 동일하며, `sync_job_details(source=NAVER)` 호출과 호환된다.

### 4.6 job_service._parse_naver_job

```python
def _parse_naver_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emp_type_raw = raw.get("empTypeCdNm")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_type_raw) if emp_type_raw else None
    return {
        "source": NAVER,
        "platform_id": int(raw["annoId"]),
        "company_id": None,
        "company_name": raw["sysCompanyCdNm"],
        "title": raw["annoSubject"],
        "location": None,
        "employment_type": employment_type,
        "annual_from": None,
        "annual_to": None,
        "job_group_id": None,
        "category_tag_id": None,
        "is_active": True,
        "created_at": None,
        "synced_at": now,
        "updated_at": None,
    }
```

`_parse_job()` 디스패처에 추가:
```python
if source == NAVER:
    return self._parse_naver_job(raw)
```

`skill_tags`는 `job_details` 테이블에 속하므로 이 단계에서 저장하지 않는다.

### 4.7 tools/naver_sync_jobs.py

```python
def naver_sync_jobs(limit_pages: int | None = DEFAULT_LIMIT_PAGES) -> str:
    engine = get_engine()
    service = JobService(engine)
    preset = service.get_preset_params(NAVER)
    if preset:
        limit_pages = preset.params.get("limit_pages", limit_pages)
    return NaverSyncer(service).sync(limit_pages=limit_pages)
```

### 4.8 sync_job_details.py 수정 후 docstring

```python
"""공고 상세정보를 동기화한다. source: WANTED (기본), NHN, NAVER. REMEMBER는 미지원."""
```

---

## 5. 에러 처리

| 상황 | 처리 방법 |
|---|---|
| 리스트 API HTTP 오류 | `raise_for_status()` → `daily_sync` try/except가 캐치 |
| `annoId` 부재/타입 오류 | `daily_sync` try/except가 캐치 (NHN과 동일한 정책) |
| 상세 페이지 모든 예외 | `fetch_job_detail()`에서 `try/except Exception` → `None` 반환 → 해당 공고 스킵 |
| BeautifulSoup 파싱 실패 | `detail_wrap` 전체 텍스트를 `requirements` fallback |
| 빈 결과 | 한국어 문자열 반환 (기존 패턴 동일) |
| `sync_applications(source=NAVER)` | `if source == NAVER` 분기에서 "네이버는 지원현황 API를 지원하지 않습니다." 반환 |

---

## 6. 테스트 전략

- `tests/test_naver_client.py`: `httpx` mock으로 리스트·상세 API 응답 검증
- `tests/test_naver_detail_syncer.py`: `_parse_naver_detail()` 단위 테스트 (HTML fixture 사용)
- `tests/test_job_service.py`: `_parse_naver_job()` 케이스 추가, `build_job_url()` NAVER 케이스 추가

---

## 7. daily_sync 통합

```python
SOURCES = [NHN, WANTED, REMEMBER, NAVER]

# 소스 디스패치 블록에 추가
elif source == NAVER:
    naver_sync()

def naver_sync():
    result = naver_sync_jobs()
    log(f"naver_sync_jobs: {result}")
```

- `sync_job_details(source=NAVER)` → `NaverDetailSyncer(service).sync(job_ids=None, limit=None)` (기존 루프 그대로)
- `sync_applications(source=NAVER)` → no-op 문자열 반환 (기존 루프 그대로)
