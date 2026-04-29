# Kakao Bank Crawler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카카오뱅크 채용공고를 목록/상세 두 단계로 동기화하는 MCP 툴을 추가한다.

**Architecture:** 기존 NHN 패턴을 그대로 따른다. `services/kakaobank/` 디렉토리에 client → syncer → detail_syncer를 두고, `tools/kakaobank_sync_jobs.py`를 MCP 툴로 노출한다. 상세 API의 HTML `contents`를 BeautifulSoup으로 파싱해 requirements/preferred_points/skill_tags를 추출한다. `job_service.py`에 `build_job_url` 헬퍼를 추가해 기존 인라인 URL 빌딩을 모두 교체한다.

**Tech Stack:** Python 3.11, httpx, beautifulsoup4 (html.parser), SQLAlchemy 2.x, FastMCP

---

### Task 1: 의존성 추가 + 상수 파일 생성

**Files:**
- Modify: `requirements.txt`
- Create: `services/kakaobank/__init__.py`
- Create: `services/kakaobank/kakaobank_constants.py`

- [ ] **Step 1: requirements.txt에 beautifulsoup4 추가**

```
beautifulsoup4>=4.12.0
```

- [ ] **Step 2: `services/kakaobank/__init__.py` 생성 (빈 파일)**

- [ ] **Step 3: `services/kakaobank/kakaobank_constants.py` 작성**

```python
KAKAO_BANK = "kakaobank"
KAKAO_BANK_JOB_BASE_URL = (
    "https://kakaobank.recruiter.co.kr/app/jobnotice/view"
    "?systemKindCode=MRS2&jobnoticeSn="
)


class KakaoBankClientConst:
    LIST_URL = "https://recruit.kakaobank.com/api/recruits"
    DETAIL_URL = "https://recruit.kakaobank.com/api/recruits/{job_id}"
    PAGE_SIZE = 20
```

- [ ] **Step 4: beautifulsoup4 설치**

```bash
pip install beautifulsoup4
```

- [ ] **Step 5: 커밋**

```bash
git add requirements.txt services/kakaobank/
git commit -m "feat: add kakaobank constants and beautifulsoup4 dependency"
```

---

### Task 2: JobService에 카카오뱅크 파서 + URL 헬퍼 추가

**Files:**
- Modify: `services/jobs/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: 실패 테스트 작성 — `test_parse_kakaobank_job`**

`tests/test_job_service.py` 하단에 추가:

```python
from services.wanted.wanted_constants import WANTED
from services.kakaobank.kakaobank_constants import KAKAO_BANK

RAW_KAKAOBANK_JOB = {
    "recruitNoticeSn": 251760,
    "recruitNoticeName": "iOS 앱 개발자",
    "recruitTypeName": "일반채용",
    "receiveStartDatetime": "2026-04-27 00:00:00",
}


def test_parse_kakaobank_job():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_KAKAOBANK_JOB, source=KAKAO_BANK)
    assert row["platform_id"] == 251760
    assert row["source"] == KAKAO_BANK
    assert row["company_name"] == "카카오뱅크"
    assert row["title"] == "iOS 앱 개발자"
    assert row["employment_type"] == "regular"
    assert row["location"] is None
    assert row["annual_from"] is None
    assert row["is_active"] is True


def test_build_job_url_kakaobank():
    service = JobService(engine=MagicMock())
    url = service.build_job_url(KAKAO_BANK, 251760)
    assert "kakaobank.recruiter.co.kr" in url
    assert "jobnoticeSn=251760" in url


def test_build_job_url_wanted():
    service = JobService(engine=MagicMock())
    url = service.build_job_url(WANTED, 12345)
    assert url == "https://www.wanted.co.kr/wd/12345"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_job_service.py::test_parse_kakaobank_job tests/test_job_service.py::test_build_job_url_kakaobank -v
```

Expected: FAIL (ImportError 또는 AttributeError)

- [ ] **Step 3: `job_service.py` 구현**

`job_service.py` 상단 import에 추가:
```python
from services.kakaobank.kakaobank_constants import KAKAO_BANK, KAKAO_BANK_JOB_BASE_URL
```

`JOB_BASE_URLS`에 카카오뱅크 추가:
```python
JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
    NHN: NHN_JOB_BASE_URL,
    KAKAO_BANK: KAKAO_BANK_JOB_BASE_URL,
}
```

`EMPLOYMENT_TYPE_MAP`에 추가:
```python
"일반채용": "regular",
```

`JobService` 클래스에 `_parse_kakaobank_job` 메서드 추가:
```python
def _parse_kakaobank_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emp_type_raw = raw.get("recruitTypeName")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_type_raw) if emp_type_raw else None
    created_at_str = raw.get("receiveStartDatetime")
    created_at = datetime.fromisoformat(created_at_str) if created_at_str else None
    return {
        "source": KAKAO_BANK,
        "platform_id": raw["recruitNoticeSn"],
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

`_parse_job` 분기에 카카오뱅크 추가:
```python
def _parse_job(self, raw: dict, source: str = WANTED) -> dict:
    if source == KAKAO_BANK:
        return self._parse_kakaobank_job(raw)
    if source == REMEMBER:
        return self._parse_remember_job(raw)
    if source == NHN:
        return self._parse_nhn_job(raw)
    return self._parse_wanted_job(raw)
```

`build_job_url` 공개 헬퍼 추가 (`KAKAO_BANK_JOB_BASE_URL` 상수 재사용, 끝에 `=`가 붙어있으므로 `/` 없이 직접 연결):
```python
def build_job_url(self, source: str, platform_id: int) -> str:
    if source == KAKAO_BANK:
        return f"{KAKAO_BANK_JOB_BASE_URL}{platform_id}"
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    return f"{base_url}/{platform_id}"
```

`get_unapplied_jobs` 내 인라인 URL 빌딩(line 307-308) 교체:
```python
# 기존
base_url = JOB_BASE_URLS.get(row["source"], WANTED_JOB_BASE_URL)
link = f"{base_url}/{row['platform_id']}"
# 교체 후
link = self.build_job_url(row["source"], row["platform_id"])
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_job_service.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/jobs/job_service.py tests/test_job_service.py
git commit -m "feat: add _parse_kakaobank_job and build_job_url to JobService"
```

---

### Task 3: get_job_candidates URL 빌딩 교체

**Files:**
- Modify: `tools/get_job_candidates.py`

- [ ] **Step 1: import 수정 + URL 빌딩 교체**

`tools/get_job_candidates.py`:

```python
# 기존 import
from services.jobs.job_service import JobService, JOB_BASE_URLS, WANTED_JOB_BASE_URL

# 교체
from services.jobs.job_service import JobService
```

line 50 교체:
```python
# 기존
"url": f"{JOB_BASE_URLS.get(c.source, WANTED_JOB_BASE_URL)}/{c.platform_id}",
# 교체
"url": service.build_job_url(c.source, c.platform_id),
```

- [ ] **Step 2: 기존 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 모든 기존 테스트 PASS

- [ ] **Step 3: 커밋**

```bash
git add tools/get_job_candidates.py
git commit -m "fix: use build_job_url in get_job_candidates"
```

---

### Task 4: KakaoBankClient 구현

**Files:**
- Create: `services/kakaobank/kakaobank_client.py`
- Create: `tests/test_kakaobank_client.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_kakaobank_client.py`:

```python
from unittest.mock import patch, MagicMock
from services.kakaobank.kakaobank_client import KakaoBankClient


def _make_list_response(page_number: int, total_pages: int, items: list) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {
        "paging": {"pageNumber": page_number, "totalPages": total_pages},
        "list": items,
    }
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_single_page():
    job = {"recruitNoticeSn": 1, "recruitNoticeName": "iOS 개발자"}
    with patch("httpx.get", return_value=_make_list_response(0, 1, [job])) as mock_get:
        client = KakaoBankClient()
        jobs = client.fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["recruitNoticeSn"] == 1
    mock_get.assert_called_once()


def test_fetch_jobs_multiple_pages():
    pages = [
        _make_list_response(0, 2, [{"recruitNoticeSn": 1}]),
        _make_list_response(1, 2, [{"recruitNoticeSn": 2}]),
    ]
    with patch("httpx.get", side_effect=pages):
        client = KakaoBankClient()
        jobs = client.fetch_jobs()
    assert len(jobs) == 2


def test_fetch_jobs_limit_pages():
    pages = [
        _make_list_response(0, 5, [{"recruitNoticeSn": 1}]),
        _make_list_response(1, 5, [{"recruitNoticeSn": 2}]),
    ]
    with patch("httpx.get", side_effect=pages):
        client = KakaoBankClient()
        jobs = client.fetch_jobs(limit_pages=2)
    assert len(jobs) == 2


def test_fetch_job_detail_success():
    detail = {"recruitNoticeSn": 1, "contents": "<p>내용</p>"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = detail
    with patch("httpx.get", return_value=mock_resp):
        client = KakaoBankClient()
        result = client.fetch_job_detail(1)
    assert result["recruitNoticeSn"] == 1


def test_fetch_job_detail_failure():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("httpx.get", return_value=mock_resp):
        client = KakaoBankClient()
        result = client.fetch_job_detail(99999)
    assert result is None
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_kakaobank_client.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: `kakaobank_client.py` 구현**

```python
import httpx
from services.kakaobank.kakaobank_constants import KakaoBankClientConst


class KakaoBankClient:
    def fetch_jobs(
        self,
        limit_pages: int | None = None,
    ) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0

        while True:
            resp = httpx.get(
                KakaoBankClientConst.LIST_URL,
                params={"pageNumber": page, "pageSize": KakaoBankClientConst.PAGE_SIZE},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            paging = data.get("paging", {})
            jobs = data.get("list") or []
            all_jobs.extend(jobs)
            page += 1

            if page >= paging.get("totalPages", 1):
                break
            if limit_pages is not None and page >= limit_pages:
                break

        return all_jobs

    def fetch_job_detail(self, job_id: int) -> dict | None:
        url = KakaoBankClientConst.DETAIL_URL.format(job_id=job_id)
        try:
            resp = httpx.get(url, timeout=30)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_kakaobank_client.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/kakaobank/kakaobank_client.py tests/test_kakaobank_client.py
git commit -m "feat: add KakaoBankClient with pagination support"
```

---

### Task 5: KakaoBankSyncer 구현

**Files:**
- Create: `services/kakaobank/kakaobank_syncer.py`
- Create: `tests/test_kakaobank_syncer.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_kakaobank_syncer.py`:

```python
from unittest.mock import MagicMock, patch
from services.kakaobank.kakaobank_syncer import KakaoBankSyncer


def test_sync_passes_full_sync_true_when_no_limit():
    service = MagicMock()
    service.upsert_jobs.return_value = "동기화 완료: 신규 1개, 변경 0개, 유지 0개"
    with patch(
        "services.kakaobank.kakaobank_syncer.KakaoBankClient"
    ) as MockClient:
        MockClient.return_value.fetch_jobs.return_value = [{"recruitNoticeSn": 1}]
        result = KakaoBankSyncer(service).sync(limit_pages=None)
    service.upsert_jobs.assert_called_once_with(
        [{"recruitNoticeSn": 1}], source="kakaobank", full_sync=True
    )
    assert "동기화 완료" in result


def test_sync_passes_full_sync_false_when_limit_set():
    service = MagicMock()
    service.upsert_jobs.return_value = "동기화 완료: 신규 0개, 변경 0개, 유지 0개"
    with patch(
        "services.kakaobank.kakaobank_syncer.KakaoBankClient"
    ) as MockClient:
        MockClient.return_value.fetch_jobs.return_value = []
        KakaoBankSyncer(service).sync(limit_pages=2)
    service.upsert_jobs.assert_called_once_with([], source="kakaobank", full_sync=False)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_kakaobank_syncer.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: `kakaobank_syncer.py` 구현**

```python
from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        client = KakaoBankClient()
        jobs = client.fetch_jobs(limit_pages=limit_pages)
        full_sync = limit_pages is None
        return self.service.upsert_jobs(jobs, source=KAKAO_BANK, full_sync=full_sync)
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/kakaobank/kakaobank_syncer.py tests/test_kakaobank_syncer.py
git commit -m "feat: add KakaoBankSyncer"
```

---

### Task 6: KakaoBankDetailSyncer 구현

**Files:**
- Create: `services/kakaobank/kakaobank_detail_syncer.py`
- Create: `tests/test_kakaobank_detail_syncer.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_kakaobank_detail_syncer.py`:

```python
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer

SAMPLE_HTML = """
<div class="desc_cont">
  <div class="tit"><b>필수 경험과 역량</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>· Swift로 개발이 가능한 분</p>
      <p>· CI/CD 경험이 있는 분</p>
    </div>
  </div>
</div>
<div class="desc_cont">
  <div class="tit"><b>우대사항</b></div>
  <div class="cont">
    <div class="inner_cont">
      <p>· Modular Architecture에 대한 이해와 관심이 있는 분</p>
    </div>
  </div>
</div>
"""

EMPTY_HTML = "<div class='desc_cont'><div class='tit'>담당할 업무</div></div>"


def test_parse_requirements():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(SAMPLE_HTML)
    assert "Swift" in result["requirements"]
    assert "CI/CD" in result["requirements"]


def test_parse_preferred_points():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(SAMPLE_HTML)
    assert "Modular Architecture" in result["preferred_points"]


def test_parse_skill_tags():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(SAMPLE_HTML)
    tags = result["skill_tags"]
    assert isinstance(tags, list)
    assert len(tags) > 0
    assert all("text" in t for t in tags)
    texts = [t["text"] for t in tags]
    assert any("Swift" in t for t in texts)


def test_parse_missing_section_returns_none():
    result = KakaoBankDetailSyncer._parse_kakaobank_detail(EMPTY_HTML)
    assert result["requirements"] is None
    assert result["preferred_points"] is None
    assert result["skill_tags"] == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_kakaobank_detail_syncer.py -v
```

Expected: FAIL (ImportError)

- [ ] **Step 3: `kakaobank_detail_syncer.py` 구현**

```python
import re
import time

from bs4 import BeautifulSoup

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankDetailSyncer(BaseSyncer):
    def sync(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> str:
        client = KakaoBankClient()
        target_pairs = self.service.get_jobs_without_details(
            source=KAKAO_BANK, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw = client.fetch_job_detail(platform_id)
            if raw is None:
                continue
            parsed = self._parse_kakaobank_detail(raw.get("contents") or "")
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
        requirements: str | None = None
        preferred_points: str | None = None

        for block in soup.find_all("div", class_="desc_cont"):
            tit_el = block.find("div", class_="tit")
            cont_el = block.find("div", class_="cont")
            if not tit_el or not cont_el:
                continue
            section = tit_el.get_text(strip=True)
            text = "\n".join(
                p.get_text(strip=True)
                for p in cont_el.find_all("p")
                if p.get_text(strip=True)
            ) or None

            if "필수 경험과 역량" in section:
                requirements = text
            elif "우대사항" in section:
                preferred_points = text

        skill_tags = []
        if requirements:
            lines = re.split(r"[·\n]", requirements)
            skill_tags = [
                {"text": line.strip()}
                for line in lines
                if line.strip()
            ]

        return {
            "requirements": requirements,
            "preferred_points": preferred_points,
            "skill_tags": skill_tags,
        }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_kakaobank_detail_syncer.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```

- [ ] **Step 6: 커밋**

```bash
git add services/kakaobank/kakaobank_detail_syncer.py tests/test_kakaobank_detail_syncer.py
git commit -m "feat: add KakaoBankDetailSyncer with HTML parsing and rough skill_tags"
```

---

### Task 7: MCP 툴 + main.py 등록

**Files:**
- Create: `tools/kakaobank_sync_jobs.py`
- Modify: `tools/sync_job_details.py`
- Modify: `main.py`

- [ ] **Step 1: `tools/kakaobank_sync_jobs.py` 작성**

```python
from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.kakaobank.kakaobank_syncer import KakaoBankSyncer


def kakaobank_sync_jobs(
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """카카오뱅크 채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(KAKAO_BANK)
    if preset:
        p = preset.params
        limit_pages = p.get("limit_pages", limit_pages)

    return KakaoBankSyncer(service).sync(limit_pages=limit_pages)


if __name__ == "__main__":
    print(kakaobank_sync_jobs())
```

- [ ] **Step 2: `tools/sync_job_details.py` 카카오뱅크 분기 추가**

```python
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer


def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: wanted (기본), nhn, kakaobank. remember는 미지원."""
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == KAKAO_BANK:
        return KakaoBankDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
```

- [ ] **Step 3: `main.py` 등록**

```python
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs

mcp.tool()(kakaobank_sync_jobs)
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add tools/kakaobank_sync_jobs.py tools/sync_job_details.py main.py
git commit -m "feat: register kakaobank MCP tools (kakaobank_sync_jobs, sync_job_details kakaobank)"
```

---

### Task 8: 스모크 테스트 (선택)

카카오뱅크 API가 실제로 응답하는지 확인한다. DB 연결 없이 클라이언트만 확인.

- [ ] **Step 1: 목록 API 직접 확인**

```bash
python -c "
from services.kakaobank.kakaobank_client import KakaoBankClient
c = KakaoBankClient()
jobs = c.fetch_jobs(limit_pages=1)
print(f'공고 수: {len(jobs)}')
print('첫 번째 공고:', jobs[0]['recruitNoticeName'] if jobs else '없음')
"
```

Expected: 공고 수 > 0

- [ ] **Step 2: 상세 API 직접 확인 (첫 번째 공고 ID 사용)**

```bash
python -c "
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer
c = KakaoBankClient()
jobs = c.fetch_jobs(limit_pages=1)
job_id = jobs[0]['recruitNoticeSn']
detail = c.fetch_job_detail(job_id)
parsed = KakaoBankDetailSyncer._parse_kakaobank_detail(detail.get('contents', ''))
print('requirements:', parsed['requirements'][:100] if parsed['requirements'] else None)
print('skill_tags:', parsed['skill_tags'][:3])
"
```

Expected: requirements 텍스트 출력, skill_tags 리스트 출력
