# Naver Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 네이버 채용공고 리스트·상세를 수집해 DB에 저장하고 기존 `get_job_candidates` 추천에 포함시킨다.

**Architecture:** NHN 패턴을 그대로 따른다. `NaverClient`가 공개 JSON API(리스트)와 HTML 상세 페이지를 수집하고, `NaverSyncer`/`NaverDetailSyncer`가 `BaseSyncer`를 구현해 `JobService`에 데이터를 넘긴다. 상세 페이지는 BeautifulSoup으로 `div.detail_box`를 파싱한다.

**Tech Stack:** Python 3.11, httpx, beautifulsoup4, SQLAlchemy 2.x, FastMCP

**Spec:** `docs/superpowers/specs/2026-05-01-naver-integration-design.md`

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| `services/naver/__init__.py` | 패키지 마커 |
| `services/naver/naver_constants.py` | URL 상수, NAVER 소스 문자열 |
| `services/naver/naver_client.py` | HTTP 수집 (리스트 JSON, 상세 HTML) |
| `services/naver/naver_syncer.py` | 리스트 동기화 (BaseSyncer) |
| `services/naver/naver_detail_syncer.py` | 상세 수집 + HTML 파싱 (BaseSyncer) |
| `tools/naver_sync_jobs.py` | MCP 툴 진입점 |
| `services/jobs/job_service.py` | `_parse_naver_job()`, `_parse_job()` 분기, `build_job_url()`, `JOB_BASE_URLS` |
| `tools/get_job_candidates.py` | URL 조합을 `build_job_url()` 사용으로 변경 |
| `tools/sync_job_details.py` | NAVER 분기 추가 |
| `tools/sync_applications.py` | NAVER no-op 분기 추가 |
| `scripts/daily_sync.py` | SOURCES 확장, `naver_sync()` 추가 |
| `main.py` | `naver_sync_jobs` 툴 등록 |
| `requirements.txt` | `beautifulsoup4` 추가 |
| `tests/test_naver_client.py` | NaverClient 단위 테스트 |
| `tests/test_naver_detail_syncer.py` | `_parse_naver_detail()` 단위 테스트 |
| `tests/test_job_service.py` (수정) | `_parse_naver_job()`, `build_job_url()` 케이스 추가 |
| `tests/test_naver_syncer.py` (신규) | NaverSyncer 단위 테스트 |

---

## Task 1: 상수 + URL 헬퍼

**Files:**
- Create: `services/naver/__init__.py`
- Create: `services/naver/naver_constants.py`
- Modify: `services/jobs/job_service.py`

- [ ] **Step 1: `services/naver/__init__.py` 생성**

```python
```
(빈 파일)

- [ ] **Step 2: `services/naver/naver_constants.py` 생성**

```python
NAVER = "naver"
NAVER_LIST_URL = "https://recruit.navercorp.com/rcrt/loadJobList.do"
NAVER_DETAIL_URL = "https://recruit.navercorp.com/rcrt/view.do"
NAVER_JOB_BASE_URL = "https://recruit.navercorp.com/rcrt/view.do?annoId="
PAGE_SIZE = 20
```

- [ ] **Step 3: `build_job_url()` 실패 테스트 작성**

`tests/test_job_service.py`에 추가:
```python
from services.jobs.job_service import build_job_url
from services.naver.naver_constants import NAVER
from services.wanted.wanted_constants import WANTED

def test_build_job_url_wanted():
    url = build_job_url(WANTED, 12345)
    assert url == "https://www.wanted.co.kr/wd/12345"

def test_build_job_url_naver():
    url = build_job_url(NAVER, 30004786)
    assert url == "https://recruit.navercorp.com/rcrt/view.do?annoId=30004786"
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
pytest tests/test_job_service.py::test_build_job_url_naver -v
```
Expected: FAIL (`ImportError: cannot import name 'build_job_url'`)

- [ ] **Step 5: `job_service.py` 수정 — `JOB_BASE_URLS` 확장 + `build_job_url()` 추가**

`services/jobs/job_service.py` 상단 import에:
```python
from services.naver.naver_constants import NAVER, NAVER_JOB_BASE_URL
```

`JOB_BASE_URLS` 딕셔너리에 NAVER 추가:
```python
JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
    NHN: NHN_JOB_BASE_URL,
    NAVER: NAVER_JOB_BASE_URL,
}
```

`JOB_BASE_URLS` 딕셔너리 바로 아래에 함수 추가:
```python
def build_job_url(source: str, platform_id: int) -> str:
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    if base_url.endswith("="):
        return f"{base_url}{platform_id}"
    return f"{base_url}/{platform_id}"
```

- [ ] **Step 6: `job_service.py` line 308 교체 — `get_unapplied_jobs` 내부**

```python
# 기존
base_url = JOB_BASE_URLS.get(row["source"], WANTED_JOB_BASE_URL)
link = f"{base_url}/{row['platform_id']}"
# 변경
link = build_job_url(row["source"], row["platform_id"])
```

- [ ] **Step 7: `get_job_candidates.py` line 50 교체**

`tools/get_job_candidates.py`의 import에 추가:
```python
from services.jobs.job_service import JobService, build_job_url
```
(기존 `JOB_BASE_URLS, WANTED_JOB_BASE_URL` import 제거)

line 50:
```python
# 기존
"url": f"{JOB_BASE_URLS.get(c.source, WANTED_JOB_BASE_URL)}/{c.platform_id}",
# 변경
"url": build_job_url(c.source, c.platform_id),
```

- [ ] **Step 8: 테스트 통과 확인**

```bash
pytest tests/test_job_service.py::test_build_job_url_wanted tests/test_job_service.py::test_build_job_url_naver -v
```
Expected: PASS 2

- [ ] **Step 9: 전체 테스트 회귀 확인**

```bash
pytest -v
```
Expected: 기존 테스트 모두 PASS

- [ ] **Step 10: 커밋**

```bash
git add services/naver/__init__.py services/naver/naver_constants.py \
        services/jobs/job_service.py tools/get_job_candidates.py \
        tests/test_job_service.py
git commit -m "feat: add naver constants and build_job_url helper"
```

---

## Task 2: NaverClient

**Files:**
- Create: `services/naver/naver_client.py`
- Create: `tests/test_naver_client.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_naver_client.py` 생성:
```python
from unittest.mock import patch, MagicMock
from services.naver.naver_client import NaverClient


MOCK_LIST_PAGE_1 = {
    "result": "Y",
    "list": [
        {
            "annoId": 30004786,
            "sysCompanyCdNm": "NAVER",
            "annoSubject": "[NAVER] 백엔드 개발자",
            "empTypeCdNm": "정규",
            "subJobCdNm": "Backend",
        }
    ],
    "totalSize": 1,
}

MOCK_DETAIL_HTML = "<html><body><div class='detail_wrap'><div class='detail_box'><h4 class='detail_title'>자격요건</h4><p class='detail_text'>Python 3년</p></div></div></body></html>"


def _mock_response(json_data=None, text_data=None, status=200):
    mock = MagicMock()
    mock.status_code = status
    if json_data is not None:
        mock.json.return_value = json_data
    if text_data is not None:
        mock.text = text_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_returns_list():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(json_data=MOCK_LIST_PAGE_1)
        client = NaverClient()
        jobs = client.fetch_jobs(limit_pages=1)
    assert len(jobs) == 1
    assert jobs[0]["annoId"] == 30004786
    assert jobs[0]["sysCompanyCdNm"] == "NAVER"


def test_fetch_jobs_stops_when_list_empty():
    empty_response = {"result": "Y", "list": [], "totalSize": 0}
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(json_data=empty_response)
        client = NaverClient()
        jobs = client.fetch_jobs()
    assert jobs == []
    assert mock_get.call_count == 1


def test_fetch_job_detail_returns_html():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_DETAIL_HTML, status=200)
        mock_get.return_value.raise_for_status = MagicMock()
        client = NaverClient()
        html = client.fetch_job_detail(30004786)
    assert html == MOCK_DETAIL_HTML


def test_fetch_job_detail_returns_none_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        client = NaverClient()
        html = client.fetch_job_detail(30004786)
    assert html is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_naver_client.py -v
```
Expected: FAIL (`ModuleNotFoundError: No module named 'services.naver.naver_client'`)

- [ ] **Step 3: `naver_client.py` 구현**

`services/naver/naver_client.py` 생성:
```python
import httpx
from constants import CRAWL_DELAY_SECONDS
import time
from services.naver.naver_constants import NAVER_LIST_URL, NAVER_DETAIL_URL, PAGE_SIZE


class NaverClient:
    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        first_index = 0
        page = 0

        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)

            params = {
                "subJobCdArr": "",
                "sysCompanyCdArr": "",
                "empTypeCdArr": "",
                "entTypeCdArr": "",
                "workAreaCdArr": "",
                "sw": "",
                "firstIndex": first_index,
            }
            resp = httpx.get(NAVER_LIST_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("list") or []
            total_size = data.get("totalSize", 0)
            all_jobs.extend(jobs)

            first_index += PAGE_SIZE
            page += 1

            if not jobs or first_index >= total_size:
                break
            if limit_pages is not None and page >= limit_pages:
                break

        return all_jobs

    def fetch_job_detail(self, anno_id: int) -> str | None:
        try:
            resp = httpx.get(
                NAVER_DETAIL_URL,
                params={"annoId": anno_id},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_naver_client.py -v
```
Expected: PASS 4

- [ ] **Step 5: 커밋**

```bash
git add services/naver/naver_client.py tests/test_naver_client.py
git commit -m "feat: add NaverClient with fetch_jobs and fetch_job_detail"
```

---

## Task 3: _parse_naver_job + job_service 통합

**Files:**
- Modify: `services/jobs/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_job_service.py`에 추가:
```python
from services.naver.naver_constants import NAVER

RAW_NAVER_JOB = {
    "annoId": 30004786,
    "sysCompanyCdNm": "NAVER",
    "annoSubject": "[NAVER] 백엔드 개발자",
    "empTypeCdNm": "정규",
    "subJobCdNm": "Backend",
}

RAW_NAVER_JOB_CONTRACT = {
    "annoId": 30004787,
    "sysCompanyCdNm": "NAVER WEBTOON",
    "annoSubject": "[웹툰] 마케터",
    "empTypeCdNm": "계약",
    "subJobCdNm": "Marketing",
}

def test_parse_naver_job():
    service = JobService(engine=MagicMock())
    row = service._parse_naver_job(RAW_NAVER_JOB)
    assert row["source"] == NAVER
    assert row["platform_id"] == 30004786
    assert row["company_name"] == "NAVER"
    assert row["title"] == "[NAVER] 백엔드 개발자"
    assert row["employment_type"] == "regular"
    assert row["location"] is None
    assert row["company_id"] is None
    assert row["is_active"] is True

def test_parse_naver_job_contract():
    service = JobService(engine=MagicMock())
    row = service._parse_naver_job(RAW_NAVER_JOB_CONTRACT)
    assert row["employment_type"] == "contract"
    assert row["company_name"] == "NAVER WEBTOON"

def test_parse_job_dispatcher_naver():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_NAVER_JOB, source=NAVER)
    assert row["source"] == NAVER
    assert row["platform_id"] == 30004786
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_job_service.py::test_parse_naver_job -v
```
Expected: FAIL (`AttributeError: 'JobService' object has no attribute '_parse_naver_job'`)

- [ ] **Step 3: `_parse_naver_job()` 구현**

`services/jobs/job_service.py`의 `EMPLOYMENT_TYPE_MAP`에 `"계약"` 추가 (네이버 API는 "계약직" 대신 "계약"을 반환):
```python
EMPLOYMENT_TYPE_MAP = {
    "정규직": "regular",
    "정규": "regular",
    "인턴": "intern",
    "계약직": "contract",
    "계약": "contract",
}
```

`services/jobs/job_service.py`에 `_parse_nhn_job()` 바로 아래에 추가:
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

`_parse_job()` 디스패처에 NAVER 분기 추가 (`if source == NHN:` 바로 아래):
```python
if source == NAVER:
    return self._parse_naver_job(raw)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_job_service.py::test_parse_naver_job \
       tests/test_job_service.py::test_parse_naver_job_contract \
       tests/test_job_service.py::test_parse_job_dispatcher_naver -v
```
Expected: PASS 3

- [ ] **Step 5: 전체 테스트 회귀 확인**

```bash
pytest -v
```
Expected: 기존 테스트 모두 PASS

- [ ] **Step 6: 커밋**

```bash
git add services/jobs/job_service.py tests/test_job_service.py
git commit -m "feat: add _parse_naver_job and NAVER dispatcher in job_service"
```

---

## Task 4: NaverSyncer

**Files:**
- Create: `services/naver/naver_syncer.py`
- Create: `tests/test_naver_syncer.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_naver_syncer.py` 생성:
```python
from unittest.mock import MagicMock, patch
from services.naver.naver_syncer import NaverSyncer
from services.naver.naver_constants import NAVER

MOCK_JOBS = [{"annoId": 30004786, "sysCompanyCdNm": "NAVER", "annoSubject": "백엔드", "empTypeCdNm": "정규", "subJobCdNm": "Backend"}]


def test_syncer_calls_upsert_with_full_sync_true_when_no_limit():
    service = MagicMock()
    with patch("services.naver.naver_syncer.NaverClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = MOCK_JOBS
        NaverSyncer(service).sync(limit_pages=None)
    service.upsert_jobs.assert_called_once_with(MOCK_JOBS, source=NAVER, full_sync=True)


def test_syncer_calls_upsert_with_full_sync_false_when_limit_set():
    service = MagicMock()
    with patch("services.naver.naver_syncer.NaverSyncer.__init__", return_value=None):
        syncer = NaverSyncer.__new__(NaverSyncer)
        syncer.service = service
    with patch("services.naver.naver_syncer.NaverClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = MOCK_JOBS
        syncer.sync(limit_pages=2)
    service.upsert_jobs.assert_called_once_with(MOCK_JOBS, source=NAVER, full_sync=False)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_naver_syncer.py -v
```
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `naver_syncer.py` 작성**

```python
from services.base_syncer import BaseSyncer
from services.naver.naver_client import NaverClient
from services.naver.naver_constants import NAVER


class NaverSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        jobs = NaverClient().fetch_jobs(limit_pages=limit_pages)
        full_sync = limit_pages is None
        return self.service.upsert_jobs(jobs, source=NAVER, full_sync=full_sync)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_naver_syncer.py -v
```
Expected: PASS 2

- [ ] **Step 5: 커밋**

```bash
git add services/naver/naver_syncer.py tests/test_naver_syncer.py
git commit -m "feat: add NaverSyncer with tests"
```

---

## Task 5: NaverDetailSyncer + HTML 파싱

**Files:**
- Create: `services/naver/naver_detail_syncer.py`
- Create: `tests/test_naver_detail_syncer.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_naver_detail_syncer.py` 생성:
```python
from services.naver.naver_detail_syncer import NaverDetailSyncer

DETAIL_HTML_FULL = """
<html><body>
<div class="detail_wrap">
  <div class="detail_box">
    <div class="detail_togglebox">
      <div class="detail_toggletitle">
        <h4 class="detail_title">자격요건</h4>
      </div>
      <div class="detail_toggleinfo">
        <p class="detail_text">Python 3년 이상</p>
      </div>
    </div>
  </div>
  <div class="detail_box">
    <div class="detail_togglebox">
      <div class="detail_toggletitle">
        <h4 class="detail_title">우대사항</h4>
      </div>
      <div class="detail_toggleinfo">
        <p class="detail_text">FastAPI 경험 우대</p>
      </div>
    </div>
  </div>
</div>
</body></html>
"""

DETAIL_HTML_NO_HEADINGS = """
<html><body>
<div class="detail_wrap">
  <div class="detail_box">
    <h4 class="detail_title"></h4>
    <p class="detail_text">공고 내용 전체</p>
  </div>
</div>
</body></html>
"""

DETAIL_HTML_EMPTY = "<html><body></body></html>"


def test_parse_naver_detail_with_sections():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_FULL)
    assert "Python 3년" in result["requirements"]
    assert "FastAPI" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_naver_detail_fallback_when_no_headings():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_NO_HEADINGS)
    assert result["requirements"] is not None
    assert "공고 내용 전체" in result["requirements"]
    assert result["preferred_points"] is None


def test_parse_naver_detail_empty_html():
    result = NaverDetailSyncer._parse_naver_detail(DETAIL_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
    assert result["skill_tags"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_naver_detail_syncer.py -v
```
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `naver_detail_syncer.py` 구현**

`services/naver/naver_detail_syncer.py` 생성:
```python
import time

from bs4 import BeautifulSoup

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.naver.naver_client import NaverClient
from services.naver.naver_constants import NAVER


class NaverDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=NAVER, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = NaverClient()
        fetched: list[JobDetail] = []

        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_naver_detail(html)
            fetched.append(JobDetail(
                job_id=internal_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=parsed["skill_tags"],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_naver_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for box in soup.select("div.detail_box"):
            title_tag = box.find("h4", class_="detail_title")
            title_text = title_tag.get_text(strip=True) if title_tag else ""
            text_tag = box.find("p", class_="detail_text")
            text = text_tag.get_text(separator="\n", strip=True) if text_tag else ""

            if "자격요건" in title_text:
                requirements = text or None
            elif "우대사항" in title_text:
                preferred_points = text or None

        if requirements is None and preferred_points is None:
            wrap = soup.select_one("div.detail_wrap")
            if wrap:
                fallback = wrap.get_text(separator="\n", strip=True)
                requirements = fallback or None

        return {
            "requirements": requirements,
            "preferred_points": preferred_points,
            "skill_tags": [],
        }
```

- [ ] **Step 4: beautifulsoup4 설치 확인 및 requirements.txt 추가**

```bash
pip show beautifulsoup4
```
설치되지 않았으면:
```bash
pip install beautifulsoup4
```

`requirements.txt`에 추가:
```
beautifulsoup4>=4.12.0
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_naver_detail_syncer.py -v
```
Expected: PASS 3

- [ ] **Step 6: 전체 테스트 회귀 확인**

```bash
pytest -v
```

- [ ] **Step 7: 커밋**

```bash
git add services/naver/naver_detail_syncer.py tests/test_naver_detail_syncer.py requirements.txt
git commit -m "feat: add NaverDetailSyncer with BeautifulSoup HTML parsing"
```

---

## Task 6: naver_sync_jobs 툴

**Files:**
- Create: `tools/naver_sync_jobs.py`

- [ ] **Step 1: `naver_sync_jobs.py` 작성**

```python
from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.naver.naver_constants import NAVER
from services.naver.naver_syncer import NaverSyncer


def naver_sync_jobs(
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """네이버 채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(NAVER)
    if preset:
        p = preset.params
        limit_pages = p.get("limit_pages", limit_pages)

    return NaverSyncer(service).sync(limit_pages=limit_pages)
```

- [ ] **Step 2: import 검증**

```bash
python -c "from tools.naver_sync_jobs import naver_sync_jobs; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add tools/naver_sync_jobs.py
git commit -m "feat: add naver_sync_jobs tool"
```

---

## Task 7: 기존 파일 통합 (sync_job_details, sync_applications, daily_sync, main.py)

**Files:**
- Modify: `tools/sync_job_details.py`
- Modify: `tools/sync_applications.py`
- Modify: `scripts/daily_sync.py`
- Modify: `main.py`

- [ ] **Step 1: `sync_job_details.py` 수정**

`tools/sync_job_details.py`:
```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.naver.naver_constants import NAVER
from services.naver.naver_detail_syncer import NaverDetailSyncer
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_detail_syncer import RememberDetailSyncer
from services.wanted.wanted_constants import WANTED
from services.wanted.wanted_detail_syncer import WantedDetailSyncer


def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: WANTED (기본), NHN, NAVER. REMEMBER는 미지원."""
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == NAVER:
        return NaverDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)


if __name__ == "__main__":
    sync_job_details(NHN)
```

- [ ] **Step 2: `sync_applications.py` 수정 — NAVER no-op 분기 추가**

`tools/sync_applications.py`:
```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.naver.naver_constants import NAVER
from services.nhn.nhn_application_syncer import NHNApplicationSyncer
from services.nhn.nhn_constants import NHN
from services.remember.remember_application_syncer import RememberApplicationSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.wanted.wanted_constants import WANTED


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본), REMEMBER, NHN."""
    engine = get_engine()
    service = JobService(engine)

    if source == REMEMBER:
        return RememberApplicationSyncer(service).sync()
    if source == NHN:
        return NHNApplicationSyncer(service).sync()
    if source == NAVER:
        return "네이버는 지원현황 API를 지원하지 않습니다."
    return WantedApplicationSyncer(service).sync()
```

- [ ] **Step 3: `daily_sync.py` 수정**

`scripts/daily_sync.py`의 import에 추가:
```python
from services.naver.naver_constants import NAVER
from tools.naver_sync_jobs import naver_sync_jobs
```

`SOURCES` 수정:
```python
SOURCES = [
    NHN,
    WANTED,
    REMEMBER,
    NAVER,
]
```

소스 디스패치 블록 전체를 아래와 같이 교체 (`else: raise RuntimeError` 앞에 NAVER 분기 추가):
```python
if source == WANTED:
    wanted_sync()
elif source == REMEMBER:
    remember_sync()
elif source == NHN:
    nhn_sync()
elif source == NAVER:
    naver_sync()
else:
    raise RuntimeError(f"정의되지 않은 source[{source}] 입니다.")
```

`naver_sync()` 함수 추가 (기존 `nhn_sync()` 함수 아래):
```python
def naver_sync():
    try:
        result = naver_sync_jobs()
        log(f"naver_sync_jobs: {result}")
    except Exception as e:
        log(f"naver_sync_jobs: 오류 - {e}")
```

- [ ] **Step 4: `main.py` 수정**

```python
from tools.naver_sync_jobs import naver_sync_jobs
```
추가 후:
```python
mcp.tool()(naver_sync_jobs)
```
`mcp.tool()(nhn_sync_jobs)` 바로 아래에 추가.

- [ ] **Step 5: 통합 검증**

```bash
python -c "
from tools.sync_job_details import sync_job_details
from tools.sync_applications import sync_applications
from scripts.daily_sync import run
from main import mcp
print('imports OK')
"
```
Expected: `imports OK`

- [ ] **Step 6: 전체 테스트 최종 확인**

```bash
pytest -v
```
Expected: 모든 테스트 PASS

- [ ] **Step 7: 커밋**

```bash
git add tools/sync_job_details.py tools/sync_applications.py \
        scripts/daily_sync.py main.py
git commit -m "feat: wire naver into sync_job_details, sync_applications, daily_sync, main"
```

---

## 완료 기준

- [ ] `pytest` 전체 통과
- [ ] `python -c "from main import mcp"` 오류 없음
- [ ] `naver_sync_jobs()` 호출 시 네이버 공고 DB 저장 확인 (수동)
- [ ] `sync_job_details(source="naver")` 호출 시 상세 수집 확인 (수동)
- [ ] `sync_applications(source="naver")` → `"네이버는 지원현황 API를 지원하지 않습니다."` 반환 확인
