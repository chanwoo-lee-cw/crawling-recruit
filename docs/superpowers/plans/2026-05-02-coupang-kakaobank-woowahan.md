# 쿠팡 · 카카오뱅크 · 우아한형제들 크롤러 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 쿠팡, 카카오뱅크, 우아한형제들 세 소스의 채용공고 수집·상세·지원현황 동기화를 기존 패턴(BaseSyncer)으로 추가한다.

**Architecture:** 각 소스는 `services/<source>/` 패키지로 격리되고, `job_service.py`의 `_parse_<source>_job()`과 `_parse_job()` 분기를 통해 DB에 저장된다. 쿠팡은 HTML 스크래핑, 카카오뱅크·우아한형제들은 공개 JSON API를 사용한다. 우아한형제들만 로그인 인증 기반 지원현황을 지원한다.

**Tech Stack:** Python 3.11, httpx, beautifulsoup4, SQLAlchemy 2.x, pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-05-02-coupang-kakaobank-woowahan-design.md`

---

## 파일 맵

### 신규 생성
```
services/coupang/__init__.py
services/coupang/coupang_constants.py
services/coupang/coupang_client.py
services/coupang/coupang_syncer.py
services/coupang/coupang_detail_syncer.py
services/coupang/coupang_application_syncer.py

services/kakaobank/__init__.py
services/kakaobank/kakaobank_constants.py
services/kakaobank/kakaobank_client.py
services/kakaobank/kakaobank_syncer.py
services/kakaobank/kakaobank_detail_syncer.py
services/kakaobank/kakaobank_application_syncer.py

services/woowahan/__init__.py
services/woowahan/woowahan_constants.py
services/woowahan/woowahan_client.py
services/woowahan/woowahan_syncer.py
services/woowahan/woowahan_detail_syncer.py
services/woowahan/woowahan_application_syncer.py

tools/coupang_sync_jobs.py
tools/kakaobank_sync_jobs.py
tools/woowahan_sync_jobs.py

tests/test_coupang_client.py
tests/test_coupang_detail_syncer.py
tests/test_kakaobank_client.py
tests/test_kakaobank_detail_syncer.py
tests/test_woowahan_client.py
tests/test_woowahan_detail_syncer.py
tests/test_woowahan_application_syncer.py
```

### 수정
```
services/jobs/job_service.py   — _parse_coupang/kakaobank/woowahan_job, _parse_job 분기, JOB_BASE_URLS
tools/sync_job_details.py      — 3개 소스 분기
tools/sync_applications.py     — 3개 소스 분기
scripts/daily_sync.py          — 3개 소스 추가
main.py                        — 3개 툴 등록
```

---

## Task 1: Coupang — constants + client

**Files:**
- Create: `services/coupang/__init__.py`
- Create: `services/coupang/coupang_constants.py`
- Create: `services/coupang/coupang_client.py`
- Test: `tests/test_coupang_client.py`

- [ ] **Step 1: constants 파일 생성**

```python
# services/coupang/__init__.py  (빈 파일)

# services/coupang/coupang_constants.py
COUPANG = "coupang"
COUPANG_LIST_URL = "https://www.coupang.jobs/kr/jobs/"
COUPANG_DETAIL_BASE_URL = "https://www.coupang.jobs/kr/jobs"
COUPANG_JOB_BASE_URL = "https://www.coupang.jobs/kr/jobs"
COUPANG_PAGE_SIZE = 500
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_coupang_client.py
from unittest.mock import patch, MagicMock
from services.coupang.coupang_client import CoupangClient

MOCK_LIST_HTML = """
<html><body>
<div class="grid job-listing" id="js-job-search-results">
  <div class="card card-job">
    <div class="card-body">
      <h2 class="card-title">
        <a class="stretched-link js-view-job" href="/kr/jobs/7230716/staff-back-end-engineer/">
          Staff Back-end Engineer
        </a>
      </h2>
      <div class="card-job-actions js-job" data-id="7230716" data-jobtitle="Staff Back-end Engineer"></div>
      <ul class="list-inline job-meta">
        <li class="list-inline-item">대한민국</li>
      </ul>
    </div>
  </div>
</div>
</body></html>
"""

MOCK_DETAIL_HTML = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <div><strong>자격 요건</strong></div>
    <ul><li>Python 3년 이상</li><li>AWS 경험</li></ul>
    <div><strong>우대 사항</strong></div>
    <ul><li>FastAPI 경험 우대</li></ul>
  </article>
</div>
</body></html>
"""


def _mock_response(text_data="", status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = text_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_parses_cards():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_LIST_HTML)
        jobs = CoupangClient().fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == 7230716
    assert jobs[0]["title"] == "Staff Back-end Engineer"
    assert jobs[0]["location"] == "대한민국"


def test_fetch_jobs_empty_page():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data="<html><body></body></html>")
        jobs = CoupangClient().fetch_jobs()
    assert jobs == []


def test_fetch_job_detail_returns_html():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_DETAIL_HTML)
        html = CoupangClient().fetch_job_detail(7230716)
    assert html == MOCK_DETAIL_HTML


def test_fetch_job_detail_returns_none_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        html = CoupangClient().fetch_job_detail(7230716)
    assert html is None
```

- [ ] **Step 3: 테스트 실행 → FAIL 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_client.py -v
```
Expected: `ImportError` (모듈 없음)

- [ ] **Step 4: CoupangClient 구현**

```python
# services/coupang/coupang_client.py
import logging
import httpx
from bs4 import BeautifulSoup
from services.coupang.coupang_constants import (
    COUPANG_LIST_URL, COUPANG_DETAIL_BASE_URL, COUPANG_PAGE_SIZE
)

logger = logging.getLogger(__name__)


class CoupangClient:
    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(
            COUPANG_LIST_URL,
            params={"search": "", "location": "South+Korea", "pagesize": COUPANG_PAGE_SIZE},
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in soup.select("div.card.card-job"):
            actions = card.select_one("div.card-job-actions.js-job")
            if not actions:
                continue
            job_id = actions.get("data-id")
            title_tag = card.select_one("h2.card-title a.js-view-job")
            title = title_tag.get_text(strip=True) if title_tag else ""
            location_tag = card.select_one("ul.list-inline li.list-inline-item")
            location = location_tag.get_text(strip=True) if location_tag else None
            if job_id and title:
                jobs.append({"id": int(job_id), "title": title, "location": location})
        if len(jobs) >= COUPANG_PAGE_SIZE:
            logger.warning("Coupang: job count >= %d, consider adding pagination", COUPANG_PAGE_SIZE)
        return jobs

    def fetch_job_detail(self, job_id: int) -> str | None:
        try:
            resp = httpx.get(f"{COUPANG_DETAIL_BASE_URL}/{job_id}", timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_client.py -v
```
Expected: 4 passed

- [ ] **Step 6: 커밋**

```bash
git add services/coupang/ tests/test_coupang_client.py
git commit -m "feat: add coupang constants and client"
```

---

## Task 2: Coupang — syncer + job_service + application_syncer + tool

**Files:**
- Create: `services/coupang/coupang_syncer.py`
- Create: `services/coupang/coupang_application_syncer.py`
- Create: `tools/coupang_sync_jobs.py`
- Modify: `services/jobs/job_service.py`

- [ ] **Step 1: 실패하는 테스트 작성 (`test_nhn.py` 패턴 참고)**

```python
# tests/test_coupang_syncer.py  (새 파일)
from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.coupang.coupang_constants import COUPANG

RAW_COUPANG_JOB = {
    "id": 7230716,
    "title": "Staff Back-end Engineer",
    "location": "대한민국",
}


def test_parse_coupang_job():
    service = JobService(engine=MagicMock())
    row = service._parse_coupang_job(RAW_COUPANG_JOB)
    assert row["source"] == COUPANG
    assert row["platform_id"] == 7230716
    assert row["title"] == "Staff Back-end Engineer"
    assert row["company_name"] == "Coupang"
    assert row["location"] == "대한민국"
    assert row["employment_type"] is None
    assert row["is_active"] is True
    assert row["synced_at"] is not None
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_syncer.py -v
```

- [ ] **Step 3: `job_service.py`에 `_parse_coupang_job` + `_parse_job` 분기 + `JOB_BASE_URLS` 추가**

`services/jobs/job_service.py` 상단 import 영역에 추가:
```python
from services.coupang.coupang_constants import COUPANG, COUPANG_JOB_BASE_URL
```

`JOB_BASE_URLS` dict에 추가:
```python
JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
    NHN: NHN_JOB_BASE_URL,
    NAVER: NAVER_JOB_BASE_URL,
    COUPANG: COUPANG_JOB_BASE_URL,
}
```

`JobService` 클래스에 메서드 추가 (`_parse_naver_job` 다음):
```python
def _parse_coupang_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "source": COUPANG,
        "platform_id": int(raw["id"]),
        "company_id": None,
        "company_name": "Coupang",
        "title": raw["title"],
        "location": raw.get("location"),
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

`_parse_job` 메서드에 분기 추가:
```python
def _parse_job(self, raw: dict, source: str = WANTED) -> dict:
    if source == REMEMBER:
        return self._parse_remember_job(raw)
    if source == NHN:
        return self._parse_nhn_job(raw)
    if source == NAVER:
        return self._parse_naver_job(raw)
    if source == COUPANG:
        return self._parse_coupang_job(raw)
    return self._parse_wanted_job(raw)
```

- [ ] **Step 4: CoupangSyncer + CoupangApplicationSyncer 구현**

```python
# services/coupang/coupang_syncer.py
from services.base_syncer import BaseSyncer
from services.coupang.coupang_client import CoupangClient
from services.coupang.coupang_constants import COUPANG


class CoupangSyncer(BaseSyncer):
    def sync(self) -> str:
        client = CoupangClient()
        jobs = client.fetch_jobs()
        return self.service.upsert_jobs(jobs, source=COUPANG, full_sync=True)
```

```python
# services/coupang/coupang_application_syncer.py
from services.base_syncer import BaseSyncer


class CoupangApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        return "쿠팡은 지원현황 API를 지원하지 않습니다."
```

- [ ] **Step 5: tool 파일 구현 (`nhn_sync_jobs.py` 참고)**

```python
# tools/coupang_sync_jobs.py
from db.connection import get_engine
from services.coupang.coupang_syncer import CoupangSyncer
from services.jobs.job_service import JobService


def coupang_sync_jobs() -> str:
    """쿠팡 채용공고를 동기화한다."""
    return CoupangSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 6: 테스트 실행 → PASS 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_syncer.py -v
```

- [ ] **Step 7: 전체 테스트 실행 (기존 테스트 깨지지 않는지 확인)**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 8: 커밋**

```bash
git add services/coupang/ tools/coupang_sync_jobs.py services/jobs/job_service.py tests/test_coupang_syncer.py
git commit -m "feat: add coupang syncer, job_service parse, and tool"
```

---

## Task 3: Coupang — detail_syncer

**Files:**
- Create: `services/coupang/coupang_detail_syncer.py`
- Test: `tests/test_coupang_detail_syncer.py`

- [ ] **Step 1: 실패하는 파싱 테스트 작성**

```python
# tests/test_coupang_detail_syncer.py
from services.coupang.coupang_detail_syncer import CoupangDetailSyncer

DETAIL_HTML_FULL = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <div><strong>자격 요건</strong></div>
    <ul>
      <li>Python 3년 이상</li>
      <li>AWS 경험</li>
    </ul>
    <div><strong>우대 사항</strong></div>
    <ul>
      <li>FastAPI 경험 우대</li>
    </ul>
  </article>
</div>
</body></html>
"""

DETAIL_HTML_NO_SECTIONS = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <p>공고 내용입니다.</p>
  </article>
</div>
</body></html>
"""

DETAIL_HTML_EMPTY = "<html><body></body></html>"


def test_parse_coupang_detail_with_sections():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_FULL)
    assert "Python 3년 이상" in result["requirements"]
    assert "AWS 경험" in result["requirements"]
    assert "FastAPI 경험 우대" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_coupang_detail_missing_sections_returns_none():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_NO_SECTIONS)
    assert result["requirements"] is None
    assert result["preferred_points"] is None


def test_parse_coupang_detail_empty_html():
    result = CoupangDetailSyncer._parse_coupang_detail(DETAIL_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
    assert result["skill_tags"] == []
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_detail_syncer.py -v
```

- [ ] **Step 3: CoupangDetailSyncer 구현**

```python
# services/coupang/coupang_detail_syncer.py
import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.coupang.coupang_client import CoupangClient
from services.coupang.coupang_constants import COUPANG


class CoupangDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=COUPANG, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = CoupangClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_coupang_detail(html)
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
    def _parse_coupang_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.select_one("div.main-col article.cms-content")
        requirements = None
        preferred_points = None

        if article:
            current_section = None
            section_lines: dict[str, list[str]] = {"requirements": [], "preferred_points": []}

            for elem in article.find_all(["strong", "li"]):
                if elem.name == "strong":
                    text = elem.get_text(strip=True)
                    if "자격 요건" in text:
                        current_section = "requirements"
                    elif "우대 사항" in text:
                        current_section = "preferred_points"
                    else:
                        current_section = None
                elif elem.name == "li" and current_section:
                    li_text = elem.get_text(strip=True)
                    if li_text:
                        section_lines[current_section].append(li_text)

            requirements = "\n".join(section_lines["requirements"]) or None
            preferred_points = "\n".join(section_lines["preferred_points"]) or None

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
.venv/bin/python -m pytest tests/test_coupang_detail_syncer.py -v
```
Expected: 3 passed

- [ ] **Step 5: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 6: 커밋**

```bash
git add services/coupang/coupang_detail_syncer.py tests/test_coupang_detail_syncer.py
git commit -m "feat: add coupang detail syncer with HTML section parsing"
```

---

## Task 4: KakaoBank — constants + client

**Files:**
- Create: `services/kakaobank/__init__.py`
- Create: `services/kakaobank/kakaobank_constants.py`
- Create: `services/kakaobank/kakaobank_client.py`
- Test: `tests/test_kakaobank_client.py`

- [ ] **Step 1: constants 파일 생성**

```python
# services/kakaobank/__init__.py  (빈 파일)

# services/kakaobank/kakaobank_constants.py
KAKAO_BANK = "kakaobank"
KAKAOBANK_LIST_URL = "https://recruit.kakaobank.com/api/recruits"
KAKAOBANK_DETAIL_URL = "https://recruit.kakaobank.com/api/recruits"
KAKAOBANK_JOB_URL = "https://kakaobank.recruiter.co.kr/app/jobnotice/view?systemKindCode=MRS2&jobnoticeSn="
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_kakaobank_client.py
from unittest.mock import patch, MagicMock
from services.kakaobank.kakaobank_client import KakaoBankClient

MOCK_LIST_PAGE_1 = {
    "paging": {"pageNumber": 0, "pageSize": 20, "totalPages": 2, "totalElements": 25},
    "list": [
        {
            "recruitNoticeSn": 251760,
            "recruitNoticeName": "iOS 앱 개발자",
            "recruitNoticeUrl": "kakaobank.recruiter.co.kr/...",
            "recruitTypeName": "일반채용",
            "recruitClassName": "Mobile",
            "receiveStartDatetime": "2026-04-27 00:00:00",
            "receiveEndDatetime": "2026-05-14 23:59:59",
        }
    ],
}
MOCK_LIST_PAGE_2 = {
    "paging": {"pageNumber": 1, "pageSize": 20, "totalPages": 2, "totalElements": 25},
    "list": [{"recruitNoticeSn": 247114, "recruitNoticeName": "서비스 기획자", "recruitTypeName": "일반채용", "recruitClassName": "Service & Biz", "receiveStartDatetime": "2026-03-09 00:00:00", "receiveEndDatetime": "2026-04-30 23:59:59", "recruitNoticeUrl": ""}],
}
MOCK_DETAIL = {
    "recruitNoticeSn": 251760,
    "recruitNoticeName": "iOS 앱 개발자",
    "recruitTypeName": "일반채용",
    "recruitClassName": "Mobile",
    "receiveStartDatetime": "2026-04-27 00:00:00",
    "receiveEndDatetime": "2026-05-14 23:59:59",
    "contents": "<div class='desc_cont'><div class='tit'>필수 경험과 역량</div><div class='cont'><p>Swift 개발 4년</p></div></div>",
}


def _mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_paginates():
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(MOCK_LIST_PAGE_1),
            _mock_response(MOCK_LIST_PAGE_2),
        ]
        jobs = KakaoBankClient().fetch_jobs()
    assert len(jobs) == 2
    assert mock_get.call_count == 2


def test_fetch_jobs_stops_when_no_more_pages():
    single_page = {
        "paging": {"pageNumber": 0, "pageSize": 20, "totalPages": 1, "totalElements": 1},
        "list": [MOCK_LIST_PAGE_1["list"][0]],
    }
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(single_page)
        jobs = KakaoBankClient().fetch_jobs()
    assert len(jobs) == 1
    assert mock_get.call_count == 1


def test_fetch_job_detail():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(MOCK_DETAIL)
        detail = KakaoBankClient().fetch_job_detail(251760)
    assert detail["recruitNoticeSn"] == 251760
    assert "contents" in detail
```

- [ ] **Step 3: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_client.py -v
```

- [ ] **Step 4: KakaoBankClient 구현**

```python
# services/kakaobank/kakaobank_client.py
import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.kakaobank.kakaobank_constants import KAKAOBANK_LIST_URL, KAKAOBANK_DETAIL_URL


class KakaoBankClient:
    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                KAKAOBANK_LIST_URL,
                params={"pageSize": 20, "pageNumber": page},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("list") or []
            all_jobs.extend(jobs)
            total_pages = data.get("paging", {}).get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
            if limit_pages is not None and page >= limit_pages:
                break
        return all_jobs

    def fetch_job_detail(self, job_id: int) -> dict | None:
        try:
            resp = httpx.get(f"{KAKAOBANK_DETAIL_URL}/{job_id}", timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
```

- [ ] **Step 5: 테스트 실행 → PASS**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_client.py -v
```

- [ ] **Step 6: 커밋**

```bash
git add services/kakaobank/ tests/test_kakaobank_client.py
git commit -m "feat: add kakaobank constants and client"
```

---

## Task 5: KakaoBank — syncer + job_service + application_syncer + tool

**Files:**
- Create: `services/kakaobank/kakaobank_syncer.py`
- Create: `services/kakaobank/kakaobank_application_syncer.py`
- Create: `tools/kakaobank_sync_jobs.py`
- Modify: `services/jobs/job_service.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_kakaobank_syncer.py  (새 파일)
from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_constants import KAKAO_BANK

RAW_KAKAOBANK_JOB = {
    "recruitNoticeSn": 251760,
    "recruitNoticeName": "iOS 앱 개발자",
    "recruitTypeName": "일반채용",
    "recruitClassName": "Mobile",
    "receiveStartDatetime": "2026-04-27 00:00:00",
    "receiveEndDatetime": "2026-05-14 23:59:59",
}


def test_parse_kakaobank_job():
    service = JobService(engine=MagicMock())
    row = service._parse_kakaobank_job(RAW_KAKAOBANK_JOB)
    assert row["source"] == KAKAO_BANK
    assert row["platform_id"] == 251760
    assert row["title"] == "iOS 앱 개발자"
    assert row["company_name"] == "카카오뱅크"
    assert row["employment_type"] == "regular"
    assert row["location"] is None
    assert row["is_active"] is True
    assert row["synced_at"] is not None
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_syncer.py -v
```

- [ ] **Step 3: `job_service.py`에 KakaoBank 관련 추가**

상단 import:
```python
from services.kakaobank.kakaobank_constants import KAKAO_BANK, KAKAOBANK_JOB_URL
```

`EMPLOYMENT_TYPE_MAP`에 추가 (이미 "일반채용" 없으면):
```python
EMPLOYMENT_TYPE_MAP = {
    ...
    "일반채용": "regular",
}
```

`JOB_BASE_URLS`에 추가:
```python
KAKAO_BANK: KAKAOBANK_JOB_URL,
```

`_parse_kakaobank_job` 메서드 추가:
```python
def _parse_kakaobank_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emp_type_raw = raw.get("recruitTypeName")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_type_raw) if emp_type_raw else None
    created_at = None
    start_str = raw.get("receiveStartDatetime")
    if start_str:
        try:
            created_at = datetime.fromisoformat(start_str)
        except ValueError:
            pass
    return {
        "source": KAKAO_BANK,
        "platform_id": int(raw["recruitNoticeSn"]),
        "company_id": None,
        "company_name": "카카오뱅크",
        "title": raw["recruitNoticeName"],
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
if source == KAKAO_BANK:
    return self._parse_kakaobank_job(raw)
```

- [ ] **Step 4: KakaoBankSyncer + KakaoBankApplicationSyncer 구현**

```python
# services/kakaobank/kakaobank_syncer.py
from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        client = KakaoBankClient()
        jobs = client.fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=KAKAO_BANK, full_sync=True)
```

```python
# services/kakaobank/kakaobank_application_syncer.py
from services.base_syncer import BaseSyncer


class KakaoBankApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        return "카카오뱅크는 지원현황 API를 지원하지 않습니다."
```

```python
# tools/kakaobank_sync_jobs.py
from db.connection import get_engine
from services.kakaobank.kakaobank_syncer import KakaoBankSyncer
from services.jobs.job_service import JobService


def kakaobank_sync_jobs() -> str:
    """카카오뱅크 채용공고를 동기화한다."""
    return KakaoBankSyncer(JobService(get_engine())).sync()
```

- [ ] **Step 5: 테스트 → PASS**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_syncer.py -v
```

- [ ] **Step 6: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 7: 커밋**

```bash
git add services/kakaobank/ tools/kakaobank_sync_jobs.py services/jobs/job_service.py tests/test_kakaobank_syncer.py
git commit -m "feat: add kakaobank syncer, job_service parse, and tool"
```

---

## Task 6: KakaoBank — detail_syncer

**Files:**
- Create: `services/kakaobank/kakaobank_detail_syncer.py`
- Test: `tests/test_kakaobank_detail_syncer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_kakaobank_detail_syncer.py
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer

# 실제 카카오뱅크 API 응답의 contents HTML 구조 (doc/kakaoBank.md 기반)
CONTENTS_HTML_FULL = """
<div class="desc_cont">
  <div class="tit"><b>담당할 업무</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>카카오뱅크 iOS 앱 서비스 개발</p>
    </div>
  </div>
</div>
<div class="desc_cont">
  <div class="tit"><b>필수 경험과 역량</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>iOS 앱 개발 4년 이상</p>
      <p>Swift 개발 가능</p>
    </div>
  </div>
</div>
<div class="desc_cont">
  <div class="tit"><b>우대사항</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>Modular Architecture 이해</p>
    </div>
  </div>
</div>
"""

CONTENTS_HTML_EMPTY = "<div></div>"


def test_parse_kakaobank_detail_extracts_sections():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(CONTENTS_HTML_FULL)
    assert "iOS 앱 개발 4년 이상" in result["requirements"]
    assert "Swift 개발 가능" in result["requirements"]
    assert "Modular Architecture" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_kakaobank_detail_missing_sections():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(CONTENTS_HTML_EMPTY)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_detail_syncer.py -v
```

- [ ] **Step 3: KakaoBankDetailSyncer 구현**

```python
# services/kakaobank/kakaobank_detail_syncer.py
import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=KAKAO_BANK, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = KakaoBankClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw_detail = client.fetch_job_detail(int(platform_id))
            if raw_detail is None:
                continue
            contents_html = raw_detail.get("contents") or ""
            parsed = self._parse_kakaobank_detail(contents_html)
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
    def _parse_kakaobank_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for block in soup.select("div.desc_cont"):
            tit_tag = block.select_one("div.tit")
            tit_text = tit_tag.get_text(strip=True) if tit_tag else ""
            cont_tag = block.select_one("div.cont")
            if not cont_tag:
                continue
            text = "\n".join(
                p.get_text(strip=True) for p in cont_tag.find_all("p") if p.get_text(strip=True)
            ) or None

            if "필수 경험과 역량" in tit_text:
                requirements = text
            elif "우대사항" in tit_text:
                preferred_points = text

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
```

- [ ] **Step 4: 테스트 → PASS**

```bash
.venv/bin/python -m pytest tests/test_kakaobank_detail_syncer.py -v
```

- [ ] **Step 5: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 6: 커밋**

```bash
git add services/kakaobank/kakaobank_detail_syncer.py tests/test_kakaobank_detail_syncer.py
git commit -m "feat: add kakaobank detail syncer with HTML section parsing"
```

---

## Task 7: Woowahan — constants + client + syncer

**Files:**
- Create: `services/woowahan/__init__.py`
- Create: `services/woowahan/woowahan_constants.py`
- Create: `services/woowahan/woowahan_client.py`
- Create: `services/woowahan/woowahan_syncer.py`
- Test: `tests/test_woowahan_client.py`
- Test: `tests/test_woowahan_syncer.py`

- [ ] **Step 1: constants 파일 생성**

```python
# services/woowahan/__init__.py  (빈 파일)

# services/woowahan/woowahan_constants.py
WOOWAHAN = "woowahan"
WOOWAHAN_LIST_URL = "https://career.woowahan.com/w1/recruits"
WOOWAHAN_DETAIL_URL = "https://career.woowahan.com/w1/recruits"
WOOWAHAN_LOGIN_URL = "https://career.woowahan.com/login"
WOOWAHAN_APPLICATIONS_URL = "https://career.woowahan.com/w1/applications"
WOOWAHAN_JOB_BASE_URL = "https://career.woowahan.com/recruit"
WOOWAHAN_DEFAULT_JOB_GROUP = "BA005001"
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# tests/test_woowahan_client.py
from unittest.mock import patch, MagicMock
from services.woowahan.woowahan_client import WoowahanClient

MOCK_LIST_PAGE_1 = {
    "code": "2000",
    "data": {
        "pageSize": 100,
        "pageNumber": 1,
        "totalPageNumber": 2,
        "totalSize": 18,
        "list": [
            {
                "recruitSeq": 24684,
                "recruitNumber": "R2604019",
                "recruitName": "Server(기술플랫폼개발)",
                "recruitOpenDate": "2026-04-20 17:30:00",
                "recruitEndDate": "9999-12-31 00:00:00",
                "employmentType": {"recruitItemGroupCode": "BA002", "recruitItemCode": "BA002001"},
                "careerType": {"recruitItemGroupCode": "BA003", "recruitItemCode": "BA003002"},
            }
        ],
    },
}
MOCK_LIST_PAGE_2 = {
    "code": "2000",
    "data": {
        "pageSize": 100, "pageNumber": 2, "totalPageNumber": 2, "totalSize": 18,
        "list": [
            {"recruitSeq": 24619, "recruitNumber": "R2411018", "recruitName": "WebFrontend", "recruitOpenDate": "2026-01-01 00:00:00", "recruitEndDate": "9999-12-31 00:00:00", "employmentType": {"recruitItemGroupCode": "BA002", "recruitItemCode": "BA002001"}, "careerType": {"recruitItemGroupCode": "BA003", "recruitItemCode": "BA003002"}},
        ],
    },
}
MOCK_DETAIL = {
    "code": "2000",
    "data": {"recruitSeq": 24619, "recruitNumber": "R2411018", "recruitName": "WebFrontend", "recruitContents": "<p>[지원자격] TypeScript 5년</p><p>[우대사항] React Native</p>"},
}


def _mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_paginates():
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(MOCK_LIST_PAGE_1),
            _mock_response(MOCK_LIST_PAGE_2),
        ]
        jobs = WoowahanClient().fetch_jobs()
    assert len(jobs) == 2
    assert mock_get.call_count == 2


def test_fetch_job_detail():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(MOCK_DETAIL)
        detail = WoowahanClient().fetch_job_detail("R2411018")
    assert detail["recruitNumber"] == "R2411018"
    assert "recruitContents" in detail
```

- [ ] **Step 3: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_woowahan_client.py -v
```

- [ ] **Step 4: WoowahanClient 구현**

```python
# services/woowahan/woowahan_client.py
import os
import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.woowahan.woowahan_constants import (
    WOOWAHAN_LIST_URL, WOOWAHAN_DETAIL_URL,
    WOOWAHAN_LOGIN_URL, WOOWAHAN_APPLICATIONS_URL,
    WOOWAHAN_DEFAULT_JOB_GROUP,
)


class WoowahanClient:
    def fetch_jobs(
        self,
        job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
        limit_pages: int | None = None,
    ) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                WOOWAHAN_LIST_URL,
                params={
                    "jobGroupCodes": job_group_codes,
                    "recruitCampaignSeq": 0,
                    "page": page,
                    "size": 100,
                    "sort": "updateDate,desc",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            jobs = data.get("list") or []
            all_jobs.extend(jobs)
            total_pages = data.get("totalPageNumber", 1)
            page += 1
            if page >= total_pages:
                break
            if limit_pages is not None and page >= limit_pages:
                break
        return all_jobs

    def fetch_job_detail(self, recruit_number: str) -> dict | None:
        try:
            resp = httpx.get(f"{WOOWAHAN_DETAIL_URL}/{recruit_number}", timeout=30)
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception:
            return None

    def login(self) -> str:
        email = os.environ.get("WOOWAHAN_EMAIL")
        password = os.environ.get("WOOWAHAN_PASSWORD")
        if not email or not password:
            raise ValueError("WOOWAHAN_EMAIL, WOOWAHAN_PASSWORD 환경변수가 설정되지 않았습니다.")
        resp = httpx.post(
            WOOWAHAN_LOGIN_URL,
            json={"applicantEmail": email, "applicantPassword": password},
            timeout=30,
        )
        resp.raise_for_status()
        cookie = resp.cookies.get("X-Authorization")
        if not cookie:
            raise PermissionError("우아한형제들 로그인 실패: X-Authorization 쿠키를 받지 못했습니다.")
        return cookie

    def fetch_applications(self, cookie: str) -> list[dict]:
        all_apps: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                WOOWAHAN_APPLICATIONS_URL,
                params={"page": page, "size": 100, "sort": "applicationDate,desc"},
                cookies={"X-Authorization": cookie},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            apps = data.get("list") or []
            all_apps.extend(apps)
            total_pages = data.get("totalPageNumber", 1)
            page += 1
            if page >= total_pages:
                break
        return all_apps
```

- [ ] **Step 5: WoowahanSyncer + _parse_woowahan_job 구현**

`services/jobs/job_service.py`에 추가:

```python
# import 영역
from services.woowahan.woowahan_constants import WOOWAHAN, WOOWAHAN_JOB_BASE_URL

# JOB_BASE_URLS
WOOWAHAN: WOOWAHAN_JOB_BASE_URL,

# 메서드 추가
def _parse_woowahan_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recruit_number = raw.get("recruitNumber", "")
    platform_id = int(recruit_number[1:]) if recruit_number.startswith("R") else int(raw["recruitSeq"])
    emp_code = (raw.get("employmentType") or {}).get("recruitItemCode", "")
    employment_type = "regular" if emp_code == "BA002001" else None
    created_at = None
    open_date = raw.get("recruitOpenDate")
    if open_date:
        try:
            created_at = datetime.fromisoformat(open_date)
        except ValueError:
            pass
    return {
        "source": WOOWAHAN,
        "platform_id": platform_id,
        "company_id": None,
        "company_name": "우아한형제들",
        "title": raw["recruitName"],
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

# _parse_job 분기
if source == WOOWAHAN:
    return self._parse_woowahan_job(raw)
```

```python
# services/woowahan/woowahan_syncer.py
from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN, WOOWAHAN_DEFAULT_JOB_GROUP


class WoowahanSyncer(BaseSyncer):
    def sync(
        self,
        job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
        limit_pages: int | None = None,
    ) -> str:
        client = WoowahanClient()
        jobs = client.fetch_jobs(job_group_codes=job_group_codes, limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=WOOWAHAN, full_sync=True)
```

- [ ] **Step 6: test_woowahan_syncer.py 작성 및 통과**

```python
# tests/test_woowahan_syncer.py
from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.woowahan.woowahan_constants import WOOWAHAN

RAW_WOOWAHAN_JOB = {
    "recruitSeq": 24684,
    "recruitNumber": "R2604019",
    "recruitName": "Server(기술플랫폼개발)",
    "recruitOpenDate": "2026-04-20 17:30:00",
    "recruitEndDate": "9999-12-31 00:00:00",
    "employmentType": {"recruitItemGroupCode": "BA002", "recruitItemCode": "BA002001"},
}


def test_parse_woowahan_job():
    service = JobService(engine=MagicMock())
    row = service._parse_woowahan_job(RAW_WOOWAHAN_JOB)
    assert row["source"] == WOOWAHAN
    assert row["platform_id"] == 2604019   # int("R2604019"[1:])
    assert row["title"] == "Server(기술플랫폼개발)"
    assert row["company_name"] == "우아한형제들"
    assert row["employment_type"] == "regular"
    assert row["is_active"] is True
```

```bash
.venv/bin/python -m pytest tests/test_woowahan_client.py tests/test_woowahan_syncer.py -v
```

- [ ] **Step 7: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 8: 커밋**

```bash
git add services/woowahan/ services/jobs/job_service.py tests/test_woowahan_client.py tests/test_woowahan_syncer.py
git commit -m "feat: add woowahan constants, client, syncer and job_service parse"
```

---

## Task 8: Woowahan — detail_syncer

**Files:**
- Create: `services/woowahan/woowahan_detail_syncer.py`
- Test: `tests/test_woowahan_detail_syncer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

핵심 검증: `platform_id`(int) → `f"R{platform_id}"` → `recruitNumber` 복원 후 상세 API 호출

```python
# tests/test_woowahan_detail_syncer.py
from services.woowahan.woowahan_detail_syncer import WoowahanDetailSyncer

RECRUIT_CONTENTS_FULL = """
<p><strong>[조직소개]</strong> CX프로덕트실 소개</p>
<p><strong>[지원자격]</strong></p>
<p>웹 프론트엔드 개발 경력 5년 이상</p>
<p>TypeScript, React 경험</p>
<p><strong>[우대사항]</strong></p>
<p>단위 테스트 경험</p>
"""

RECRUIT_CONTENTS_NO_SECTIONS = "<p>일반 공고 내용</p>"


def test_parse_woowahan_detail_extracts_sections():
    result = WoowahanDetailSyncer._parse_woowahan_detail(RECRUIT_CONTENTS_FULL)
    assert "웹 프론트엔드 개발 경력 5년 이상" in result["requirements"]
    assert "TypeScript, React 경험" in result["requirements"]
    assert "단위 테스트 경험" in result["preferred_points"]
    assert result["skill_tags"] == []


def test_parse_woowahan_detail_missing_sections():
    result = WoowahanDetailSyncer._parse_woowahan_detail(RECRUIT_CONTENTS_NO_SECTIONS)
    assert result["requirements"] is None
    assert result["preferred_points"] is None


def test_recruit_number_reconstructed_from_platform_id():
    """platform_id(int) → f"R{platform_id}" = recruitNumber."""
    platform_id = 2411018
    recruit_number = f"R{platform_id}"
    assert recruit_number == "R2411018"
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_woowahan_detail_syncer.py -v
```

- [ ] **Step 3: WoowahanDetailSyncer 구현**

```python
# services/woowahan/woowahan_detail_syncer.py
import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN


class WoowahanDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=WOOWAHAN, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = WoowahanClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            recruit_number = f"R{platform_id}"
            raw_detail = client.fetch_job_detail(recruit_number)
            if raw_detail is None:
                continue
            contents_html = raw_detail.get("recruitContents") or ""
            parsed = self._parse_woowahan_detail(contents_html)
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
    def _parse_woowahan_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None
        current_section = None
        section_lines: dict[str, list[str]] = {"requirements": [], "preferred_points": []}

        for elem in soup.find_all(["strong", "p"]):
            if elem.name == "strong":
                text = elem.get_text(strip=True)
                if "[지원자격]" in text:
                    current_section = "requirements"
                elif "[우대사항]" in text:
                    current_section = "preferred_points"
                else:
                    current_section = None
            elif elem.name == "p" and current_section:
                # <strong> 포함된 <p>는 섹션 헤더이므로 건너뜀
                if elem.find("strong"):
                    continue
                text = elem.get_text(strip=True)
                if text:
                    section_lines[current_section].append(text)

        requirements = "\n".join(section_lines["requirements"]) or None
        preferred_points = "\n".join(section_lines["preferred_points"]) or None

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
```

- [ ] **Step 4: 테스트 → PASS**

```bash
.venv/bin/python -m pytest tests/test_woowahan_detail_syncer.py -v
```

- [ ] **Step 5: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 6: 커밋**

```bash
git add services/woowahan/woowahan_detail_syncer.py tests/test_woowahan_detail_syncer.py
git commit -m "feat: add woowahan detail syncer with recruitNumber reconstruction"
```

---

## Task 9: Woowahan — application_syncer + tool

**Files:**
- Create: `services/woowahan/woowahan_application_syncer.py`
- Create: `tools/woowahan_sync_jobs.py`
- Modify: `services/jobs/job_service.py` (`_parse_woowahan_applications` 추가)
- Test: `tests/test_woowahan_application_syncer.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tests/test_woowahan_application_syncer.py
from unittest.mock import patch, MagicMock
from services.jobs.job_service import JobService
from services.woowahan.woowahan_constants import WOOWAHAN

RAW_WOOWAHAN_APPS = [
    {
        "applicationSeq": 100251475,
        "applicationDate": "2025-08-12 04:05:16",
        "applicationFinalYn": True,
        "applicationJudgmentStatesCode": {"code": "PASS", "text": "서류합격"},
        "recruitSeq": 22451,
        "recruitNumber": "R2409006",
        "recruitName": "백엔드 개발",
        "isEndedRecruit": False,
    },
    {
        "applicationSeq": 100262742,
        "applicationDate": "2026-01-06 21:03:53",
        "applicationFinalYn": False,   # 임시저장 → skip
        "applicationJudgmentStatesCode": {"code": "TEMPORARY", "text": "임시저장"},
        "recruitSeq": 23189,
        "recruitNumber": "R2509015",
        "recruitName": "서버 개발",
        "isEndedRecruit": False,
    },
]


def test_parse_woowahan_applications_skips_temporary():
    service = JobService(engine=MagicMock())
    result = service._parse_woowahan_applications(RAW_WOOWAHAN_APPS)
    assert len(result) == 1
    assert result[0]["platform_id"] == 100251475
    assert result[0]["job_platform_id"] == 2409006   # int("R2409006"[1:])
    assert result[0]["status"] == "PASS"
    assert result[0]["apply_time_str"] == "2025-08-12 04:05:16"
```

- [ ] **Step 2: 테스트 실행 → FAIL**

```bash
.venv/bin/python -m pytest tests/test_woowahan_application_syncer.py -v
```

- [ ] **Step 3: `job_service.py`에 `_parse_woowahan_applications` + `_parse_applications` 분기 추가**

```python
# 메서드 추가
def _parse_woowahan_applications(self, raw_apps: list[dict]) -> list[dict]:
    result = []
    for app in raw_apps:
        if not app.get("applicationFinalYn"):
            continue
        recruit_number = app.get("recruitNumber", "")
        job_platform_id = int(recruit_number[1:]) if recruit_number.startswith("R") else None
        if job_platform_id is None:
            continue
        result.append({
            "job_platform_id": job_platform_id,
            "platform_id": app["applicationSeq"],
            "status": app["applicationJudgmentStatesCode"]["code"],
            "apply_time_str": app.get("applicationDate"),
        })
    return result

# _parse_applications 분기 추가 (WOOWAHAN은 Task 7에서 이미 import됨)
if source == WOOWAHAN:
    return self._parse_woowahan_applications(raw_apps)
```

- [ ] **Step 4: WoowahanApplicationSyncer + woowahan_sync_jobs 구현**

```python
# services/woowahan/woowahan_application_syncer.py
from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN


class WoowahanApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = WoowahanClient()
            cookie = client.login()
            apps = client.fetch_applications(cookie)
            return self.service.upsert_applications(apps, source=WOOWAHAN)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
```

```python
# tools/woowahan_sync_jobs.py
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.woowahan.woowahan_constants import WOOWAHAN_DEFAULT_JOB_GROUP
from services.woowahan.woowahan_syncer import WoowahanSyncer


def woowahan_sync_jobs(
    job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
) -> str:
    """우아한형제들 채용공고를 동기화한다."""
    return WoowahanSyncer(JobService(get_engine())).sync(job_group_codes=job_group_codes)
```

- [ ] **Step 5: 테스트 → PASS**

```bash
.venv/bin/python -m pytest tests/test_woowahan_application_syncer.py -v
```

- [ ] **Step 6: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```

- [ ] **Step 7: 커밋**

```bash
git add services/woowahan/ tools/woowahan_sync_jobs.py services/jobs/job_service.py tests/test_woowahan_application_syncer.py
git commit -m "feat: add woowahan application syncer, tool, and job_service parse"
```

---

## Task 10: 통합 — sync_job_details + sync_applications + daily_sync + main.py

**Files:**
- Modify: `tools/sync_job_details.py`
- Modify: `tools/sync_applications.py`
- Modify: `scripts/daily_sync.py`
- Modify: `main.py`

- [ ] **Step 1: `sync_job_details.py` 분기 추가**

```python
# tools/sync_job_details.py  수정 후 전체
from db.connection import get_engine
from services.coupang.coupang_constants import COUPANG
from services.coupang.coupang_detail_syncer import CoupangDetailSyncer
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer
from services.naver.naver_constants import NAVER
from services.naver.naver_detail_syncer import NaverDetailSyncer
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_detail_syncer import RememberDetailSyncer
from services.wanted.wanted_constants import WANTED
from services.wanted.wanted_detail_syncer import WantedDetailSyncer
from services.woowahan.woowahan_constants import WOOWAHAN
from services.woowahan.woowahan_detail_syncer import WoowahanDetailSyncer


def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: WANTED (기본), REMEMBER, NHN, NAVER, COUPANG, KAKAO_BANK, WOOWAHAN."""
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == NAVER:
        return NaverDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == COUPANG:
        return CoupangDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == KAKAO_BANK:
        return KakaoBankDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == WOOWAHAN:
        return WoowahanDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)


if __name__ == "__main__":
    sync_job_details(NHN)
```

- [ ] **Step 2: `sync_applications.py` 분기 추가**

```python
# tools/sync_applications.py 수정 후 전체
from db.connection import get_engine
from services.coupang.coupang_application_syncer import CoupangApplicationSyncer
from services.coupang.coupang_constants import COUPANG
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_application_syncer import KakaoBankApplicationSyncer
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.naver.naver_constants import NAVER
from services.nhn.nhn_application_syncer import NHNApplicationSyncer
from services.nhn.nhn_constants import NHN
from services.remember.remember_application_syncer import RememberApplicationSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.wanted.wanted_constants import WANTED
from services.woowahan.woowahan_application_syncer import WoowahanApplicationSyncer
from services.woowahan.woowahan_constants import WOOWAHAN


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다."""
    engine = get_engine()
    service = JobService(engine)
    if source == REMEMBER:
        return RememberApplicationSyncer(service).sync()
    if source == NHN:
        return NHNApplicationSyncer(service).sync()
    if source == NAVER:
        return "네이버는 지원현황 API를 지원하지 않습니다."
    if source == COUPANG:
        return CoupangApplicationSyncer(service).sync()
    if source == KAKAO_BANK:
        return KakaoBankApplicationSyncer(service).sync()
    if source == WOOWAHAN:
        return WoowahanApplicationSyncer(service).sync()
    return WantedApplicationSyncer(service).sync()
```

- [ ] **Step 3: `daily_sync.py`에 3개 소스 추가**

기존 `daily_sync.py`에서 다음 내용 추가:

import 영역에 추가:
```python
from services.coupang.coupang_constants import COUPANG
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.woowahan.woowahan_constants import WOOWAHAN
from tools.coupang_sync_jobs import coupang_sync_jobs
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs
from tools.woowahan_sync_jobs import woowahan_sync_jobs
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
]
```

`run()` 함수 내 분기에 추가:
```python
elif source == COUPANG:
    coupang_sync()
elif source == KAKAO_BANK:
    kakaobank_sync()
elif source == WOOWAHAN:
    woowahan_sync()
```

세 함수 추가:
```python
def coupang_sync():
    try:
        result = coupang_sync_jobs()
        log(f"coupang_sync_jobs: {result}")
    except Exception as e:
        log(f"coupang_sync_jobs: 오류 - {e}")


def kakaobank_sync():
    try:
        result = kakaobank_sync_jobs()
        log(f"kakaobank_sync_jobs: {result}")
    except Exception as e:
        log(f"kakaobank_sync_jobs: 오류 - {e}")


def woowahan_sync():
    try:
        result = woowahan_sync_jobs()
        log(f"woowahan_sync_jobs: {result}")
    except Exception as e:
        log(f"woowahan_sync_jobs: 오류 - {e}")
```

- [ ] **Step 4: `main.py`에 3개 툴 등록**

```python
# main.py에 import 추가
from tools.coupang_sync_jobs import coupang_sync_jobs
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs
from tools.woowahan_sync_jobs import woowahan_sync_jobs

# mcp.tool() 등록 추가 (기존 라인들 다음)
mcp.tool()(coupang_sync_jobs)
mcp.tool()(kakaobank_sync_jobs)
mcp.tool()(woowahan_sync_jobs)
```

- [ ] **Step 5: `test_daily_sync.py` 확인 및 업데이트**

기존 `tests/test_daily_sync.py`의 `run()` 호출 테스트에서 3개 신규 sync 함수를 mock 추가해야 한다. 기존 파일을 읽어 `@patch` 데코레이터에 다음 3개를 추가한다:

```python
@patch("scripts.daily_sync.coupang_sync_jobs", return_value="coupang ok")
@patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="kakaobank ok")
@patch("scripts.daily_sync.woowahan_sync_jobs", return_value="woowahan ok")
```

그리고 assertions에도 3개 소스 추가 (기존 테스트의 `sources` 변수명과 동일하게):
```python
assert COUPANG in sources
assert KAKAO_BANK in sources
assert WOOWAHAN in sources
```

테스트 실행:
```bash
.venv/bin/python -m pytest tests/test_daily_sync.py -v
```

Expected: 기존 + 신규 assertions 모두 PASS

- [ ] **Step 6: 전체 테스트**

```bash
.venv/bin/python -m pytest -v
```
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add tools/sync_job_details.py tools/sync_applications.py scripts/daily_sync.py main.py tests/test_daily_sync.py
git commit -m "feat: wire coupang, kakaobank, woowahan into sync tools and daily_sync"
```
