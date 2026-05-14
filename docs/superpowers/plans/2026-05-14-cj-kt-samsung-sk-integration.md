# CJ / KT / 삼성 / SK 채용 소스 연동 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CJ, KT, 삼성, SK 4개 채용 플랫폼을 기존 소스 추가 패턴(constants → client → syncer → detail_syncer → application_syncer → tool → wire-up)으로 연동한다.

**Architecture:** 각 소스는 `services/<source>/` 패키지로 격리. CJ·KT는 목록 전용(상세 없음), 삼성은 HTML 목록 + JSON 상세 API, SK는 JSON 목록 + HTML 상세 파싱. `build_job_url`에 CJ·SK용 prefix 포매터를 추가해 기존 URL 생성 로직을 확장.

**Tech Stack:** Python 3.11, httpx (sync), beautifulsoup4, SQLAlchemy 2.x, pytest, FastMCP

---

## 파일 구조

### 신규 생성
```
services/cj/__init__.py
services/cj/cj_constants.py
services/cj/cj_client.py
services/cj/cj_syncer.py
services/cj/cj_detail_syncer.py
services/cj/cj_application_syncer.py

services/kt/__init__.py
services/kt/kt_constants.py
services/kt/kt_client.py
services/kt/kt_syncer.py
services/kt/kt_detail_syncer.py
services/kt/kt_application_syncer.py

services/samsung/__init__.py
services/samsung/samsung_constants.py
services/samsung/samsung_client.py
services/samsung/samsung_syncer.py
services/samsung/samsung_detail_syncer.py
services/samsung/samsung_application_syncer.py

services/sk/__init__.py
services/sk/sk_constants.py
services/sk/sk_client.py
services/sk/sk_syncer.py
services/sk/sk_detail_syncer.py
services/sk/sk_application_syncer.py

tools/cj_sync_jobs.py
tools/kt_sync_jobs.py
tools/samsung_sync_jobs.py
tools/sk_sync_jobs.py

tests/test_cj.py
tests/test_kt.py
tests/test_samsung.py
tests/test_sk.py
```

### 기존 수정
```
services/jobs/job_service.py   — _parse_cj_job, _parse_kt_job, _parse_samsung_job, _parse_sk_job 추가, JOB_BASE_URLS / JOB_URL_FORMATTERS 추가, build_job_url 수정
tools/sync_job_details.py      — CJ, KT, SAMSUNG, SK 분기 추가
tools/sync_applications.py     — CJ, KT, SAMSUNG, SK 분기 추가
scripts/daily_sync.py          — SOURCES 리스트 및 sync 함수 추가
main.py                        — 4개 tool 등록
```

---

## Task 1: CJ 소스

**API 특성:**
- 목록: `POST https://recruit.cj.net/recruit/ko/recruit/recruit/searchNewGonggoList.fo` (JSON body)
- IT 직군 필터: `arrRecJob: "IR"`
- 페이지네이션: body의 `pageVal`(1-based), `pageIndex`(10). 응답 각 item에 `tot_cnt`(전체 개수) 포함
- platform_id: `int(zz_jo_num[1:])` — "J20260319037841" → 20260319037841
- job URL: `https://recruit.cj.net/recruit/ko/recruit/recruit/jobDetail.fo?zz_jo_num=J{platform_id}`
- 상세/지원현황: 미지원

**Files:**
- Create: `services/cj/cj_constants.py`, `services/cj/cj_client.py`, `services/cj/cj_syncer.py`, `services/cj/cj_detail_syncer.py`, `services/cj/cj_application_syncer.py`, `services/cj/__init__.py`, `tools/cj_sync_jobs.py`
- Modify: `services/jobs/job_service.py`
- Test: `tests/test_cj.py`

- [ ] **Step 1: 패키지 파일 생성**

`services/cj/__init__.py` — 빈 파일

`services/cj/cj_constants.py`:
```python
CJ = "cj"
CJ_LIST_URL = "https://recruit.cj.net/recruit/ko/recruit/recruit/searchNewGonggoList.fo"
CJ_JOB_URL_PREFIX = "https://recruit.cj.net/recruit/ko/recruit/recruit/jobDetail.fo?zz_jo_num=J"
CJ_PAGE_SIZE = 10
```

`services/cj/cj_client.py`:
```python
import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.cj.cj_constants import CJ_LIST_URL, CJ_PAGE_SIZE


class CJClient:
    _HEADERS = {"Content-Type": "application/json"}

    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        page = 1
        total = None
        while True:
            if page > 1:
                time.sleep(CRAWL_DELAY_SECONDS)
            body = {
                "pageVal": str(page),
                "pageIndex": str(CJ_PAGE_SIZE),
                "orderDesc": "1",
                "sch_title": "",
                "arrGubun": "",
                "arrRecBu": "",
                "arrRecJob": "IR",
                "arrRecArea": "",
                "schArea": "Y",
                "recJobbox": "IR",
            }
            resp = httpx.post(CJ_LIST_URL, json=body, headers=self._HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("ds_newRecruitList") or []
            if total is None and jobs:
                total = int(jobs[0].get("tot_cnt", 0))
            all_jobs.extend(jobs)
            if not jobs or len(all_jobs) >= (total or 0):
                break
            if limit_pages is not None and page >= limit_pages:
                break
            page += 1
        return all_jobs
```

`services/cj/cj_syncer.py`:
```python
from services.base_syncer import BaseSyncer
from services.cj.cj_client import CJClient
from services.cj.cj_constants import CJ


class CJSyncer(BaseSyncer):
    async def sync(self, limit_pages: int | None = None) -> str:
        client = CJClient()
        jobs = client.fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=CJ, full_sync=True)
```

`services/cj/cj_detail_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class CJDetailSyncer(BaseSyncer):
    async def sync(self, **kwargs) -> str:
        return "CJ는 상세 동기화를 지원하지 않습니다."
```

`services/cj/cj_application_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class CJApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "CJ는 지원현황 API를 지원하지 않습니다."
```

`tools/cj_sync_jobs.py`:
```python
from db.connection import get_engine
from services.cj.cj_syncer import CJSyncer
from services.jobs.job_service import JobService


async def cj_sync_jobs() -> str:
    """CJ 채용공고를 동기화한다."""
    return await CJSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 2: `_parse_cj_job` 추가 (`services/jobs/job_service.py`)**

파일 상단 import에 추가:
```python
from services.cj.cj_constants import CJ, CJ_JOB_URL_PREFIX
```

`JOB_BASE_URLS` dict 다음에 `JOB_URL_FORMATTERS` dict와 수정된 `build_job_url` 추가:
```python
# platform_id로 단순 prefix+id 조합이 안 되는 소스용 포매터
JOB_URL_FORMATTERS: dict[str, callable] = {}

def build_job_url(source: str, platform_id: int) -> str:
    if source in JOB_URL_FORMATTERS:
        return JOB_URL_FORMATTERS[source](platform_id)
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    if base_url.endswith("="):
        return f"{base_url}{platform_id}"
    return f"{base_url}/{platform_id}"
```

그리고 `_parse_cj_job` 메서드 추가:
```python
def _parse_cj_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    zz_jo_num = raw.get("zz_jo_num", "")
    platform_id = int(zz_jo_num[1:]) if zz_jo_num.startswith("J") else int(zz_jo_num)
    emp_code = raw.get("zz_jo_type")  # "A" = 경력 등 (미매핑 시 None)
    return {
        "source": CJ,
        "platform_id": platform_id,
        "company_id": None,
        "company_name": raw.get("compnm", "CJ"),
        "title": raw.get("zz_title", ""),
        "location": raw.get("location_cd_nm"),
        "employment_type": None,
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

`_parse_job` 분기에 추가:
```python
if source == CJ:
    return self._parse_cj_job(raw)
```

`JOB_BASE_URLS`에 추가 (CJ는 특수 포매터 사용하므로 fallback URL만):
```python
CJ: "https://recruit.cj.net",
```

그리고 모듈 레벨에서 `JOB_URL_FORMATTERS` 등록:
```python
JOB_URL_FORMATTERS[CJ] = lambda pid: f"{CJ_JOB_URL_PREFIX}{pid}"
```

- [ ] **Step 3: 실패 테스트 작성 (`tests/test_cj.py`)**

```python
from unittest.mock import MagicMock, patch


def test_cj_client_fetch_jobs_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ds_newRecruitList": [
            {"zz_jo_num": "J20260319037841", "zz_title": "Backend Dev", "compnm": "CJ ENM",
             "location_cd_nm": "서울", "tot_cnt": 1}
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("services.cj.cj_client.httpx.post", return_value=mock_response):
        from services.cj.cj_client import CJClient
        jobs = CJClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["zz_jo_num"] == "J20260319037841"


def test_parse_cj_job():
    from services.jobs.job_service import JobService
    raw = {
        "zz_jo_num": "J20260319037841",
        "zz_title": "Backend Dev",
        "compnm": "CJ ENM",
        "location_cd_nm": "서울",
        "tot_cnt": 1,
    }
    result = JobService.__new__(JobService)._parse_cj_job(raw)
    assert result["source"] == "cj"
    assert result["platform_id"] == 20260319037841
    assert result["title"] == "Backend Dev"
    assert result["company_name"] == "CJ ENM"
    assert result["location"] == "서울"


def test_cj_syncer_calls_upsert():
    with patch("services.cj.cj_syncer.CJClient") as MockClient, \
         patch("services.cj.cj_syncer.BaseSyncer.__init__", return_value=None):
        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = [{"zz_jo_num": "J123", "zz_title": "Dev"}]
        MockClient.return_value = mock_client

        from services.cj.cj_syncer import CJSyncer
        import asyncio
        syncer = CJSyncer.__new__(CJSyncer)
        syncer.service = MagicMock()
        syncer.service.upsert_jobs.return_value = "동기화 완료: 신규 1개"
        result = asyncio.run(syncer.sync())

    assert "동기화" in result
    syncer.service.upsert_jobs.assert_called_once()


def test_cj_detail_syncer_returns_message():
    import asyncio
    from services.cj.cj_detail_syncer import CJDetailSyncer
    syncer = CJDetailSyncer.__new__(CJDetailSyncer)
    syncer.service = MagicMock()
    result = asyncio.run(syncer.sync())
    assert "지원하지 않습니다" in result


def test_build_job_url_cj():
    from services.jobs.job_service import build_job_url
    url = build_job_url("cj", 20260319037841)
    assert "J20260319037841" in url
    assert "recruit.cj.net" in url
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_cj.py -v
```
Expected: 5개 FAILED (ImportError 또는 AssertionError)

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_cj.py -v
```
Expected: 5개 PASSED

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
.venv/bin/python -m pytest -q
```
Expected: all passed

- [ ] **Step 7: 커밋**

```bash
git add services/cj/ tools/cj_sync_jobs.py tests/test_cj.py services/jobs/job_service.py
git commit -m "feat: add CJ job source (list-only sync)"
```

---

## Task 2: KT 소스

**API 특성:**
- 목록: `GET https://recruit.kt.com/api/recruit?isPost=1&isInprogress=1&isContainsContents=0`
- 응답: `data` 배열, 한 번에 전부 반환 (페이지네이션 없음)
- platform_id: `int(recruitNoticeUrl.rsplit("/", 1)[-1])` — "https://kt.recruiter.co.kr/career/jobs/107620" → 107620
- job URL: `https://kt.recruiter.co.kr/career/jobs/{platform_id}`
- 상세/지원현황: 미지원

**Files:**
- Create: `services/kt/__init__.py`, `services/kt/kt_constants.py`, `services/kt/kt_client.py`, `services/kt/kt_syncer.py`, `services/kt/kt_detail_syncer.py`, `services/kt/kt_application_syncer.py`, `tools/kt_sync_jobs.py`
- Modify: `services/jobs/job_service.py`
- Test: `tests/test_kt.py`

- [ ] **Step 1: 패키지 파일 생성**

`services/kt/__init__.py` — 빈 파일

`services/kt/kt_constants.py`:
```python
KT = "kt"
KT_LIST_URL = "https://recruit.kt.com/api/recruit"
KT_JOB_BASE_URL = "https://kt.recruiter.co.kr/career/jobs"
```

`services/kt/kt_client.py`:
```python
import httpx
from services.kt.kt_constants import KT_LIST_URL


class KTClient:
    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(
            KT_LIST_URL,
            params={"isPost": 1, "isInprogress": 1, "isContainsContents": 0},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or []
```

`services/kt/kt_syncer.py`:
```python
from services.base_syncer import BaseSyncer
from services.kt.kt_client import KTClient
from services.kt.kt_constants import KT


class KTSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = KTClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=KT, full_sync=True)
```

`services/kt/kt_detail_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class KTDetailSyncer(BaseSyncer):
    async def sync(self, **kwargs) -> str:
        return "KT는 상세 동기화를 지원하지 않습니다."
```

`services/kt/kt_application_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class KTApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "KT는 지원현황 API를 지원하지 않습니다."
```

`tools/kt_sync_jobs.py`:
```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.kt.kt_syncer import KTSyncer


async def kt_sync_jobs() -> str:
    """KT 채용공고를 동기화한다."""
    return await KTSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 2: `_parse_kt_job` 추가 (`services/jobs/job_service.py`)**

import 추가:
```python
from services.kt.kt_constants import KT, KT_JOB_BASE_URL
```

`JOB_BASE_URLS`에 추가:
```python
KT: KT_JOB_BASE_URL,
```

`_parse_kt_job` 메서드:
```python
def _parse_kt_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notice_url = raw.get("recruitNoticeUrl", "")
    platform_id = int(notice_url.rsplit("/", 1)[-1]) if notice_url and "/" in notice_url else raw.get("recruitNoticeSn", 0)
    emp_raw = raw.get("recruitClassName")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_raw) if emp_raw else None
    created_at = None
    start_str = raw.get("receiveStartDatetime")
    if start_str:
        try:
            created_at = datetime.fromisoformat(start_str)
        except ValueError:
            pass
    return {
        "source": KT,
        "platform_id": int(platform_id),
        "company_id": None,
        "company_name": raw.get("company") or "KT",
        "title": raw.get("title") or raw.get("recruitNoticeName", ""),
        "location": None,
        "employment_type": employment_type,
        "annual_from": None,
        "annual_to": None,
        "job_group_id": None,
        "category_tag_id": None,
        "is_active": True,
        "created_at": created_at,
        "synced_at": now,
        "updated_at": None,
    }
```

`_parse_job` 분기 추가:
```python
if source == KT:
    return self._parse_kt_job(raw)
```

- [ ] **Step 3: 실패 테스트 작성 (`tests/test_kt.py`)**

```python
from unittest.mock import MagicMock, patch


def test_kt_client_fetch_jobs():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "isSuccess": True,
        "data": [
            {
                "recruitNoticeSn": 251744,
                "recruitNoticeName": "[kt] 백엔드 개발자 채용",
                "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
                "recruitClassName": "경력",
                "receiveStartDatetime": "2026-04-23 10:00:00",
                "company": "KT",
                "title": "백엔드 개발자",
            }
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("services.kt.kt_client.httpx.get", return_value=mock_resp):
        from services.kt.kt_client import KTClient
        jobs = KTClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["recruitNoticeSn"] == 251744


def test_parse_kt_job():
    from services.jobs.job_service import JobService
    raw = {
        "recruitNoticeSn": 251744,
        "recruitNoticeName": "[kt] 백엔드 개발자 채용",
        "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
        "recruitClassName": "경력",
        "receiveStartDatetime": "2026-04-23 10:00:00",
        "company": "KT",
        "title": "백엔드 개발자",
    }
    result = JobService.__new__(JobService)._parse_kt_job(raw)
    assert result["source"] == "kt"
    assert result["platform_id"] == 107620
    assert result["title"] == "백엔드 개발자"
    assert result["company_name"] == "KT"


def test_build_job_url_kt():
    from services.jobs.job_service import build_job_url
    url = build_job_url("kt", 107620)
    assert "kt.recruiter.co.kr" in url
    assert "107620" in url
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_kt.py -v
```
Expected: FAILED

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_kt.py -v
```
Expected: all PASSED

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 7: 커밋**

```bash
git add services/kt/ tools/kt_sync_jobs.py tests/test_kt.py services/jobs/job_service.py
git commit -m "feat: add KT job source (list-only sync)"
```

---

## Task 3: 삼성 소스

**API 특성:**
- 목록: `GET https://www.samsungcareers.com/hr/list.data` → HTML 응답
  - 각 `<li>` 내 `<a data-value="22,248">` → platform_id = int("22,248".replace(",","")) = 22248
  - `<p class="company">` → company_name
  - `<h3 class="title">` → title
  - `<span>` (class 없음) in `<p class="info">` → employment_type text
  - `<span class="period">` → 날짜 문자열 (저장 안 함, is_active 판단용)
- 상세: `GET https://www.samsungcareers.com/recruit/detail.data?seqno={platform_id}&strCode=` → JSON
  - `data.result.qlfctKr` — 공통 자격요건
  - `data.items[].titleKr` + `data.items[].qlfctKr` — 포지션별 자격요건
  - `data.items[].titleKr` + `data.items[].favorKr` — 포지션별 우대사항
  - requirements = 전체 qlfctKr 합산, preferred_points = 전체 favorKr 합산
- job URL: `https://www.samsungcareers.com/recruit/detail.html?seqno={platform_id}`
- 지원현황: 미지원

**Files:**
- Create: `services/samsung/__init__.py`, `services/samsung/samsung_constants.py`, `services/samsung/samsung_client.py`, `services/samsung/samsung_syncer.py`, `services/samsung/samsung_detail_syncer.py`, `services/samsung/samsung_application_syncer.py`, `tools/samsung_sync_jobs.py`
- Modify: `services/jobs/job_service.py`
- Test: `tests/test_samsung.py`

- [ ] **Step 1: 패키지 파일 생성**

`services/samsung/__init__.py` — 빈 파일

`services/samsung/samsung_constants.py`:
```python
SAMSUNG = "samsung"
SAMSUNG_LIST_URL = "https://www.samsungcareers.com/hr/list.data"
SAMSUNG_DETAIL_URL = "https://www.samsungcareers.com/recruit/detail.data"
SAMSUNG_JOB_BASE_URL = "https://www.samsungcareers.com/recruit/detail.html?seqno="
```

`services/samsung/samsung_client.py`:
```python
import time
import httpx
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from services.samsung.samsung_constants import SAMSUNG_LIST_URL, SAMSUNG_DETAIL_URL


class SamsungClient:
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(SAMSUNG_LIST_URL, headers=self._HEADERS, timeout=30)
        resp.raise_for_status()
        return self._parse_list_html(resp.text)

    @staticmethod
    def _parse_list_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        for li in soup.select("li"):
            a_tag = li.select_one("a[data-value]")
            if not a_tag:
                continue
            raw_id = a_tag.get("data-value", "").replace(",", "").strip()
            if not raw_id.isdigit():
                continue
            company_tag = li.select_one("p.company")
            title_tag = li.select_one("h3.title")
            info_tag = li.select_one("p.info")
            emp_span = None
            if info_tag:
                emp_span = info_tag.find("span", class_=False)
                if emp_span is None:
                    emp_span = info_tag.find("span")
            jobs.append({
                "id": int(raw_id),
                "company": company_tag.get_text(strip=True) if company_tag else "삼성",
                "title": title_tag.get_text(strip=True) if title_tag else "",
                "employment_type": emp_span.get_text(strip=True) if emp_span else None,
            })
        return jobs

    def fetch_job_detail(self, platform_id: int) -> dict | None:
        try:
            resp = httpx.get(
                SAMSUNG_DETAIL_URL,
                params={"seqno": platform_id, "strCode": ""},
                headers=self._HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception:
            return None
```

`services/samsung/samsung_syncer.py`:
```python
from services.base_syncer import BaseSyncer
from services.samsung.samsung_client import SamsungClient
from services.samsung.samsung_constants import SAMSUNG


class SamsungSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = SamsungClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=SAMSUNG, full_sync=True)
```

`services/samsung/samsung_detail_syncer.py`:
```python
import time
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.samsung.samsung_client import SamsungClient
from services.samsung.samsung_constants import SAMSUNG


class SamsungDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=SAMSUNG, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = SamsungClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw = client.fetch_job_detail(int(platform_id))
            if raw is None:
                continue
            parsed = self._parse_detail(raw)
            fetched.append(JobDetail(
                job_id=internal_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=[],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_detail(data: dict) -> dict:
        result = data.get("result") or {}
        items = data.get("items") or []

        req_parts = []
        if result.get("qlfctKr"):
            req_parts.append(result["qlfctKr"])
        for item in items:
            title = item.get("titleKr", "")
            qlfct = (item.get("qlfctKr") or "").strip()
            if qlfct:
                req_parts.append(f"[{title}]\n{qlfct}" if title else qlfct)

        favor_parts = []
        for item in items:
            title = item.get("titleKr", "")
            favor = (item.get("favorKr") or "").strip()
            if favor:
                favor_parts.append(f"[{title}]\n{favor}" if title else favor)

        return {
            "requirements": "\n\n".join(req_parts) or None,
            "preferred_points": "\n\n".join(favor_parts) or None,
        }
```

`services/samsung/samsung_application_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class SamsungApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "삼성은 지원현황 API를 지원하지 않습니다."
```

`tools/samsung_sync_jobs.py`:
```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.samsung.samsung_syncer import SamsungSyncer


async def samsung_sync_jobs() -> str:
    """삼성 채용공고를 동기화한다."""
    return await SamsungSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 2: `_parse_samsung_job` 추가 (`services/jobs/job_service.py`)**

import 추가:
```python
from services.samsung.samsung_constants import SAMSUNG, SAMSUNG_JOB_BASE_URL
```

`JOB_BASE_URLS`에 추가:
```python
SAMSUNG: SAMSUNG_JOB_BASE_URL,
```

> 참고: `SAMSUNG_JOB_BASE_URL`은 `"...?seqno="` 로 끝나므로 기존 `endswith("=")` 분기로 처리됨.

`_parse_samsung_job` 메서드:
```python
def _parse_samsung_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emp_raw = raw.get("employment_type")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_raw) if emp_raw else None
    return {
        "source": SAMSUNG,
        "platform_id": int(raw["id"]),
        "company_id": None,
        "company_name": raw.get("company", "삼성"),
        "title": raw.get("title", ""),
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

`_parse_job` 분기 추가:
```python
if source == SAMSUNG:
    return self._parse_samsung_job(raw)
```

- [ ] **Step 3: 실패 테스트 작성 (`tests/test_samsung.py`)**

```python
from unittest.mock import MagicMock, patch

SAMPLE_LIST_HTML = """
<ul>
  <li>
    <div>
      <a href="/#none" data-value="22,248">
        <p class="company">삼성SDI</p>
        <h3 class="title">경력사원 채용</h3>
        <p class="info">
          <span>경력</span>
          <span class="period">2026.05.04 ~ 2026.05.18</span>
        </p>
      </a>
    </div>
  </li>
</ul>
"""

SAMPLE_DETAIL_JSON = {
    "result": {"seq": 22248, "qlfctKr": "공통 자격요건"},
    "items": [
        {"titleKr": "포지션A", "qlfctKr": "Python 3년", "favorKr": "ML 경험"},
        {"titleKr": "포지션B", "qlfctKr": "Java 5년", "favorKr": "MSA 경험"},
    ],
}


def test_samsung_client_parse_list_html():
    from services.samsung.samsung_client import SamsungClient
    jobs = SamsungClient._parse_list_html(SAMPLE_LIST_HTML)
    assert len(jobs) == 1
    assert jobs[0]["id"] == 22248
    assert jobs[0]["company"] == "삼성SDI"
    assert jobs[0]["title"] == "경력사원 채용"
    assert jobs[0]["employment_type"] == "경력"


def test_parse_samsung_job():
    from services.jobs.job_service import JobService
    raw = {"id": 22248, "company": "삼성SDI", "title": "경력사원 채용", "employment_type": "경력"}
    result = JobService.__new__(JobService)._parse_samsung_job(raw)
    assert result["source"] == "samsung"
    assert result["platform_id"] == 22248
    assert result["title"] == "경력사원 채용"
    assert result["employment_type"] is None  # "경력" not in EMPLOYMENT_TYPE_MAP (경력 직군이지 계약 유형 아님)


def test_samsung_detail_syncer_parse_detail():
    from services.samsung.samsung_detail_syncer import SamsungDetailSyncer
    parsed = SamsungDetailSyncer._parse_detail(SAMPLE_DETAIL_JSON)
    assert "공통 자격요건" in parsed["requirements"]
    assert "Python 3년" in parsed["requirements"]
    assert "Java 5년" in parsed["requirements"]
    assert "ML 경험" in parsed["preferred_points"]
    assert "MSA 경험" in parsed["preferred_points"]


def test_build_job_url_samsung():
    from services.jobs.job_service import build_job_url
    url = build_job_url("samsung", 22248)
    assert "samsungcareers.com" in url
    assert "22248" in url
    assert "seqno=" in url
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_samsung.py -v
```
Expected: FAILED

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_samsung.py -v
```
Expected: all PASSED

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 7: 커밋**

```bash
git add services/samsung/ tools/samsung_sync_jobs.py tests/test_samsung.py services/jobs/job_service.py
git commit -m "feat: add Samsung job source (list + detail sync)"
```

---

## Task 4: SK 소스

**API 특성:**
- 목록: `POST https://www.skcareers.com/Recruit/GetRecruitList` (form-encoded body)
  - body: `sort=2&searchText=&corpCode=&jobRole=0&recruitType=&workingType=&workingRegion=`
  - 응답: `list` 배열, 한 번에 전부 반환
  - platform_id: `int(noticeID[1:])` — "R260107" → 260107
  - job URL: `https://www.skcareers.com/Recruit/Detail/R{platform_id}`
- 상세: `GET https://www.skcareers.com/Recruit/Detail/R{platform_id}` → HTML
  - `<h3 class="detail-content-title">이런 분과 함께 하고 싶습니다.</h3>` 블록 내 `<ul class="asset-list">` → requirements
  - `<h3 class="detail-content-title">이런 경험이 있다면 더 환영합니다.</h3>` 블록 내 `<ul class="asset-list">` → preferred_points
- 지원현황: 미지원

**Files:**
- Create: `services/sk/__init__.py`, `services/sk/sk_constants.py`, `services/sk/sk_client.py`, `services/sk/sk_syncer.py`, `services/sk/sk_detail_syncer.py`, `services/sk/sk_application_syncer.py`, `tools/sk_sync_jobs.py`
- Modify: `services/jobs/job_service.py`
- Test: `tests/test_sk.py`

- [ ] **Step 1: 패키지 파일 생성**

`services/sk/__init__.py` — 빈 파일

`services/sk/sk_constants.py`:
```python
SK = "sk"
SK_LIST_URL = "https://www.skcareers.com/Recruit/GetRecruitList"
SK_DETAIL_BASE_URL = "https://www.skcareers.com/Recruit/Detail/R"
SK_JOB_URL_PREFIX = "https://www.skcareers.com/Recruit/Detail/R"
```

`services/sk/sk_client.py`:
```python
import httpx
from bs4 import BeautifulSoup
from services.sk.sk_constants import SK_LIST_URL, SK_DETAIL_BASE_URL


class SKClient:
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def fetch_jobs(self) -> list[dict]:
        resp = httpx.post(
            SK_LIST_URL,
            data={
                "sort": "2",
                "searchText": "",
                "corpCode": "",
                "jobRole": "0",
                "recruitType": "",
                "workingType": "",
                "workingRegion": "",
            },
            headers=self._HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("list") or []

    def fetch_job_detail(self, platform_id: int) -> str | None:
        try:
            resp = httpx.get(
                f"{SK_DETAIL_BASE_URL}{platform_id}",
                headers=self._HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
```

`services/sk/sk_syncer.py`:
```python
from services.base_syncer import BaseSyncer
from services.sk.sk_client import SKClient
from services.sk.sk_constants import SK


class SKSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = SKClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=SK, full_sync=True)
```

`services/sk/sk_detail_syncer.py`:
```python
import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.sk.sk_client import SKClient
from services.sk.sk_constants import SK


class SKDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=SK, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = SKClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_detail_html(html)
            fetched.append(JobDetail(
                job_id=internal_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=[],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_detail_html(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for section in soup.select("div.detail-content-item"):
            h3 = section.select_one("h3.detail-content-title")
            if not h3:
                continue
            h3_text = h3.get_text(strip=True)
            items = [li.get_text(strip=True) for li in section.select("ul.asset-list li") if li.get_text(strip=True)]
            text = "\n".join(items) or None
            if "함께 하고 싶습니다" in h3_text:
                requirements = text
            elif "경험이 있다면" in h3_text:
                preferred_points = text

        return {"requirements": requirements, "preferred_points": preferred_points}
```

`services/sk/sk_application_syncer.py`:
```python
from services.base_syncer import BaseSyncer


class SKApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "SK는 지원현황 API를 지원하지 않습니다."
```

`tools/sk_sync_jobs.py`:
```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.sk.sk_syncer import SKSyncer


async def sk_sync_jobs() -> str:
    """SK 채용공고를 동기화한다."""
    return await SKSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 2: `_parse_sk_job` 추가 (`services/jobs/job_service.py`)**

import 추가:
```python
from services.sk.sk_constants import SK, SK_JOB_URL_PREFIX
```

`JOB_URL_FORMATTERS` 등록 (모듈 레벨):
```python
JOB_URL_FORMATTERS[SK] = lambda pid: f"{SK_JOB_URL_PREFIX}{pid}"
```

`_parse_sk_job` 메서드:
```python
def _parse_sk_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    notice_id = raw.get("noticeID", "")
    platform_id = int(notice_id[1:]) if notice_id.startswith("R") else raw.get("jobNoticeNo", 0)
    emp_raw = raw.get("workingType")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_raw) if emp_raw else None
    return {
        "source": SK,
        "platform_id": int(platform_id),
        "company_id": None,
        "company_name": raw.get("corpName", "SK"),
        "title": raw.get("title", ""),
        "location": raw.get("workingArea"),
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

`_parse_job` 분기 추가:
```python
if source == SK:
    return self._parse_sk_job(raw)
```

- [ ] **Step 3: 실패 테스트 작성 (`tests/test_sk.py`)**

```python
from unittest.mock import MagicMock, patch

SAMPLE_DETAIL_HTML = """
<div class="detail-content-item">
  <h3 class="detail-content-title">이런 분과 함께 하고 싶습니다.</h3>
  <div class="item-column">
    <strong class="item-label">지원자격</strong>
    <div class="item-field">
      <ul class="asset-list">
        <li>DevOps 경력 5년 이상</li>
        <li>Kubernetes 운영 경험</li>
      </ul>
    </div>
  </div>
</div>
<div class="detail-content-item">
  <h3 class="detail-content-title">이런 경험이 있다면 더 환영합니다.</h3>
  <div class="item-column">
    <ul class="asset-list">
      <li>Karpenter 경험</li>
      <li>ArgoCD 경험</li>
    </ul>
  </div>
</div>
"""


def test_sk_client_fetch_jobs():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "list": [
            {"jobNoticeNo": 4559, "noticeID": "R260107", "title": "DevOps Engineer",
             "corpName": "티맵모빌리티", "workingType": "정규", "workingArea": "서울"}
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("services.sk.sk_client.httpx.post", return_value=mock_resp):
        from services.sk.sk_client import SKClient
        jobs = SKClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["noticeID"] == "R260107"


def test_parse_sk_job():
    from services.jobs.job_service import JobService
    raw = {"jobNoticeNo": 4559, "noticeID": "R260107", "title": "DevOps Engineer",
           "corpName": "티맵모빌리티", "workingType": "정규", "workingArea": "서울"}
    result = JobService.__new__(JobService)._parse_sk_job(raw)
    assert result["source"] == "sk"
    assert result["platform_id"] == 260107
    assert result["title"] == "DevOps Engineer"
    assert result["company_name"] == "티맵모빌리티"
    assert result["employment_type"] == "regular"
    assert result["location"] == "서울"


def test_sk_detail_syncer_parse_html():
    from services.sk.sk_detail_syncer import SKDetailSyncer
    parsed = SKDetailSyncer._parse_detail_html(SAMPLE_DETAIL_HTML)
    assert "DevOps 경력 5년 이상" in parsed["requirements"]
    assert "Kubernetes 운영 경험" in parsed["requirements"]
    assert "Karpenter 경험" in parsed["preferred_points"]
    assert "ArgoCD 경험" in parsed["preferred_points"]


def test_build_job_url_sk():
    from services.jobs.job_service import build_job_url
    url = build_job_url("sk", 260107)
    assert "skcareers.com" in url
    assert "R260107" in url
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
.venv/bin/python -m pytest tests/test_sk.py -v
```
Expected: FAILED

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_sk.py -v
```
Expected: all PASSED

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 7: 커밋**

```bash
git add services/sk/ tools/sk_sync_jobs.py tests/test_sk.py services/jobs/job_service.py
git commit -m "feat: add SK job source (list + detail sync)"
```

---

## Task 5: 기존 파일 연결

**Files:**
- Modify: `tools/sync_job_details.py`, `tools/sync_applications.py`, `scripts/daily_sync.py`, `main.py`

- [ ] **Step 1: `tools/sync_job_details.py` 업데이트**

상단 import에 추가:
```python
from services.cj.cj_constants import CJ
from services.cj.cj_detail_syncer import CJDetailSyncer
from services.kt.kt_constants import KT
from services.kt.kt_detail_syncer import KTDetailSyncer
from services.samsung.samsung_constants import SAMSUNG
from services.samsung.samsung_detail_syncer import SamsungDetailSyncer
from services.sk.sk_constants import SK
from services.sk.sk_detail_syncer import SKDetailSyncer
```

`sync_job_details` 함수 내에 분기 추가 (기존 `if source == REMEMBER:` 앞에):
```python
if source == CJ:
    return await CJDetailSyncer(service).sync()
if source == KT:
    return await KTDetailSyncer(service).sync()
if source == SAMSUNG:
    return SamsungDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
if source == SK:
    return SKDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
```

- [ ] **Step 2: `tools/sync_applications.py` 업데이트**

import 추가:
```python
from services.cj.cj_application_syncer import CJApplicationSyncer
from services.cj.cj_constants import CJ
from services.kt.kt_application_syncer import KTApplicationSyncer
from services.kt.kt_constants import KT
from services.samsung.samsung_application_syncer import SamsungApplicationSyncer
from services.samsung.samsung_constants import SAMSUNG
from services.sk.sk_application_syncer import SKApplicationSyncer
from services.sk.sk_constants import SK
```

`sync_applications` 함수에 분기 추가:
```python
if source == CJ:
    return await CJApplicationSyncer(service).sync()
if source == KT:
    return await KTApplicationSyncer(service).sync()
if source == SAMSUNG:
    return await SamsungApplicationSyncer(service).sync()
if source == SK:
    return await SKApplicationSyncer(service).sync()
```

- [ ] **Step 3: `scripts/daily_sync.py` 업데이트**

import 추가:
```python
from services.cj.cj_constants import CJ
from services.kt.kt_constants import KT
from services.samsung.samsung_constants import SAMSUNG
from services.sk.sk_constants import SK
from tools.cj_sync_jobs import cj_sync_jobs
from tools.kt_sync_jobs import kt_sync_jobs
from tools.samsung_sync_jobs import samsung_sync_jobs
from tools.sk_sync_jobs import sk_sync_jobs
```

`SOURCES` 리스트에 추가:
```python
SOURCES = [
    NHN,
    WANTED,
    REMEMBER,
    NAVER,
    COUPANG,
    KAKAO_BANK,
    WOOWAHAN,
    CJ,
    KT,
    SAMSUNG,
    SK,
]
```

`run()` 함수의 source 분기에 추가:
```python
elif source == CJ:
    await cj_sync()
elif source == KT:
    await kt_sync()
elif source == SAMSUNG:
    await samsung_sync()
elif source == SK:
    await sk_sync()
```

파일 하단에 새 sync 함수 추가:
```python
async def cj_sync():
    try:
        result = await cj_sync_jobs()
        log(f"cj_sync_jobs: {result}")
    except Exception as e:
        log(f"cj_sync_jobs: 오류 - {e}")


async def kt_sync():
    try:
        result = await kt_sync_jobs()
        log(f"kt_sync_jobs: {result}")
    except Exception as e:
        log(f"kt_sync_jobs: 오류 - {e}")


async def samsung_sync():
    try:
        result = await samsung_sync_jobs()
        log(f"samsung_sync_jobs: {result}")
    except Exception as e:
        log(f"samsung_sync_jobs: 오류 - {e}")


async def sk_sync():
    try:
        result = await sk_sync_jobs()
        log(f"sk_sync_jobs: {result}")
    except Exception as e:
        log(f"sk_sync_jobs: 오류 - {e}")
```

- [ ] **Step 4: `main.py` 업데이트**

import 추가:
```python
from tools.cj_sync_jobs import cj_sync_jobs
from tools.kt_sync_jobs import kt_sync_jobs
from tools.samsung_sync_jobs import samsung_sync_jobs
from tools.sk_sync_jobs import sk_sync_jobs
```

tool 등록 추가:
```python
mcp.tool()(cj_sync_jobs)
mcp.tool()(kt_sync_jobs)
mcp.tool()(samsung_sync_jobs)
mcp.tool()(sk_sync_jobs)
```

- [ ] **Step 5: 전체 테스트 회귀 확인**

```bash
.venv/bin/python -m pytest -q
```
Expected: all passed (기존 테스트 포함)

- [ ] **Step 6: `daily_sync.py` smoke test (DB 불필요)**

```bash
.venv/bin/python -c "
from scripts.daily_sync import SOURCES
from services.cj.cj_constants import CJ
from services.kt.kt_constants import KT
from services.samsung.samsung_constants import SAMSUNG
from services.sk.sk_constants import SK
assert CJ in SOURCES
assert KT in SOURCES
assert SAMSUNG in SOURCES
assert SK in SOURCES
print('SOURCES OK:', SOURCES)
"
```
Expected: `SOURCES OK: [...]` 출력

- [ ] **Step 7: `main.py` import smoke test**

```bash
.venv/bin/python -c "import main; print('main.py import OK')"
```
Expected: `main.py import OK`

- [ ] **Step 8: 커밋**

```bash
git add tools/sync_job_details.py tools/sync_applications.py scripts/daily_sync.py main.py
git commit -m "feat: wire CJ/KT/Samsung/SK into sync_job_details, sync_applications, daily_sync, main"
```

---

## 완료 체크리스트

- [ ] `tests/test_cj.py` 전부 PASS
- [ ] `tests/test_kt.py` 전부 PASS
- [ ] `tests/test_samsung.py` 전부 PASS
- [ ] `tests/test_sk.py` 전부 PASS
- [ ] 전체 `pytest -q` PASS (기존 포함)
- [ ] `main.py` import 정상
- [ ] `daily_sync.py` SOURCES 포함 확인
