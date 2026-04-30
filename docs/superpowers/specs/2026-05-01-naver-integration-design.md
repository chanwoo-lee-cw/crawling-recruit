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
- `firstIndex`: 오프셋 페이지네이션 (0부터 시작)
- 응답: `{ "result": "Y", "list": [...], "totalSize": N }`
- `list`가 비거나 `firstIndex >= totalSize`이면 수집 종료

주요 응답 필드:

| 필드 | 설명 |
|---|---|
| `annoId` | 공고 ID (platform_id) |
| `sysCompanyCdNm` | 회사명 (NAVER, NAVER WEBTOON 등) |
| `annoSubject` | 공고 제목 |
| `empTypeCdNm` | 고용형태 (정규, 계약, 인턴) |
| `subJobCdNm` | 직무 카테고리 (skill_tags 원본) |
| `jobDetailLink` | 상세 페이지 URL |

### 2.2 채용공고 상세

```
GET https://recruit.navercorp.com/rcrt/view.do?annoId={annoId}
```

- HTML 응답, BeautifulSoup으로 파싱
- `div.detail_wrap > div.detail_box` 순회
  - `h4.detail_title` 텍스트에 "자격요건" 포함 → `requirements`
  - `h4.detail_title` 텍스트에 "우대사항" 포함 → `preferred_points`
  - 매칭 없으면 첫 번째 박스 텍스트를 `requirements` fallback

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
| `services/jobs/job_service.py` | `_parse_naver_job()` 추가, `JOB_BASE_URLS`에 NAVER 추가 |
| `scripts/daily_sync.py` | `SOURCES`에 NAVER 추가, `naver_sync()` 함수 추가 |
| `main.py` | `naver_sync_jobs` 툴 등록 |
| `tools/sync_job_details.py` | NAVER 소스 라우팅 추가 |
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

### 4.2 NaverClient

```python
class NaverClient:
    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        # firstIndex를 PAGE_SIZE씩 증가
        # list가 비거나 firstIndex >= totalSize이면 종료
        # limit_pages 도달 시 조기 종료

    def fetch_job_detail(self, anno_id: int) -> str | None:
        # HTML 반환, 실패 시 None
```

### 4.3 NaverSyncer

```python
class NaverSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        jobs = NaverClient().fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=NAVER, full_sync=limit_pages is None)
```

### 4.4 NaverDetailSyncer

```python
class NaverDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        # get_jobs_without_details(source=NAVER)
        # 각 공고마다 fetch_job_detail() → _parse_naver_detail() → upsert_job_details()
        # CRAWL_DELAY_SECONDS 적용

    @staticmethod
    def _parse_naver_detail(html: str) -> dict:
        # BeautifulSoup으로 div.detail_box 순회
        # returns: {"requirements": ..., "preferred_points": ..., "skill_tags": [...]}
```

### 4.5 job_service._parse_naver_job

```python
def _parse_naver_job(self, raw: dict) -> dict:
    # annoId → platform_id (int)
    # sysCompanyCdNm → company_name
    # annoSubject → title
    # empTypeCdNm → employment_type (EMPLOYMENT_TYPE_MAP 변환)
    # source = NAVER
```

`skill_tags`는 리스트 API의 `subJobCdNm`을 저장하되, detail syncer 실행 시 덮어쓴다.

---

## 5. 에러 처리

| 상황 | 처리 방법 |
|---|---|
| 리스트 API HTTP 오류 | `raise_for_status()` → daily_sync try/except가 캐치 |
| 상세 페이지 HTTP 오류/타임아웃 | `None` 반환 → 해당 공고 스킵 |
| BeautifulSoup 파싱 실패 | `detail_wrap` 전체 텍스트를 `requirements` fallback |
| 빈 결과 | 한국어 문자열 반환 (기존 패턴 동일) |

---

## 6. 테스트 전략

- `tests/test_naver_client.py`: `httpx` mock으로 리스트·상세 API 검증
- `tests/test_naver_detail_syncer.py`: `_parse_naver_detail()` 단위 테스트 (HTML fixture 사용)
- `tests/test_job_service.py`: `_parse_naver_job()` 케이스 추가

---

## 7. daily_sync 통합

```python
SOURCES = [NHN, WANTED, REMEMBER, NAVER]

def naver_sync():
    result = naver_sync_jobs()
    log(f"naver_sync_jobs: {result}")
```

`sync_job_details(source=NAVER)` 및 `sync_applications(source=NAVER)`는 기존 루프에서 자동으로 처리된다. (단, 네이버는 지원현황 API가 없으므로 `sync_applications`는 no-op으로 처리)
