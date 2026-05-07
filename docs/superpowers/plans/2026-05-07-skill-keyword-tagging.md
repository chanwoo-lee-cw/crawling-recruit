# Skill Keyword Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `requirements`/`preferred_points` 텍스트를 DB 저장 키워드 사전으로 스캔해서 `skill_tags`를 자동 보강하고, MCP 툴로 키워드를 관리할 수 있게 한다.

**Architecture:** `skill_keywords` 테이블에 키워드를 저장하고 3개 MCP 툴로 CRUD. `sync_job_details` 실행 시 `enrich_skill_tags`가 키워드 목록을 받아 텍스트 스캔 후 `skill_tags`에 병합. 기존 매칭/스코어링 로직 변경 없음.

**Tech Stack:** SQLAlchemy 2.x (`DeclarativeBase`, `Mapped`, `mapped_column`), FastMCP, pytest, unittest.mock

---

## 파일 구조

| 파일 | 변경 유형 |
|---|---|
| `db/models/skill_keyword.py` | 신규 |
| `db/models/__init__.py` | 수정 (`SkillKeyword` import + `__all__` 추가) |
| `db/repositories/skill_keyword_repository.py` | 신규 |
| `services/jobs/job_service.py` | 수정 (메서드 4개 추가, `import re` 추가) |
| `tools/add_skill_keyword.py` | 신규 |
| `tools/list_skill_keywords.py` | 신규 |
| `tools/delete_skill_keyword.py` | 신규 |
| `tools/sync_job_details.py` | 수정 (enrichment 단계 삽입) |
| `main.py` | 수정 (툴 3개 등록) |
| `tests/test_job_service.py` | 수정 (테스트 9개 추가) |
| `tests/test_tools.py` | 수정 (테스트 2개 추가 + 기존 2개 수정) |

---

## Task 1: SkillKeyword 모델 + Repository 생성

**Files:**
- Create: `db/models/skill_keyword.py`
- Modify: `db/models/__init__.py`
- Create: `db/repositories/skill_keyword_repository.py`
- Test: `tests/test_job_service.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_job_service.py` 하단에 추가:

```python
def test_add_keyword():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None  # 미존재
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.add_keyword("Python")
    assert result == "키워드가 추가되었습니다: Python"
    mock_session.add.assert_called_once()


def test_add_keyword_duplicate():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = MagicMock()  # 이미 존재
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.add_keyword("Python")
    assert result == "이미 존재하는 키워드입니다: Python"


def test_list_keywords():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = ["AWS", "Python"]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.list_keywords()
    assert result == ["AWS", "Python"]


def test_delete_keyword():
    mock_kw = MagicMock()
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = mock_kw
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.delete_keyword("Python")
    assert result == "키워드가 삭제되었습니다: Python"
    mock_session.delete.assert_called_once_with(mock_kw)


def test_delete_keyword_not_found():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.delete_keyword("Go")
    assert result == "존재하지 않는 키워드입니다: Go"


def test_enrich_skill_tags_adds_matched_keywords():
    service = JobService(engine=MagicMock())
    detail = JobDetail(
        job_id=1,
        requirements="Python 3년 이상. MySQL 경험 필수.",
        preferred_points="Docker 경험자 우대",
        skill_tags=[{"text": "Python"}],
    )
    result = service.enrich_skill_tags(detail, ["Python", "MySQL", "Docker", "AWS"])
    texts = [t["text"] for t in result.skill_tags]
    assert "Python" in texts   # 기존 태그 유지
    assert "MySQL" in texts    # requirements에서 추출
    assert "Docker" in texts   # preferred_points에서 추출
    assert "AWS" not in texts  # 텍스트에 없음


def test_enrich_skill_tags_empty_keywords():
    service = JobService(engine=MagicMock())
    detail = JobDetail(
        job_id=1,
        requirements="Python 3년 이상",
        preferred_points=None,
        skill_tags=[{"text": "Python"}],
    )
    result = service.enrich_skill_tags(detail, [])
    assert result.skill_tags == [{"text": "Python"}]


def test_enrich_skill_tags_no_duplicate():
    service = JobService(engine=MagicMock())
    detail = JobDetail(
        job_id=1,
        requirements="python 경험 필수",  # 소문자
        preferred_points=None,
        skill_tags=[{"text": "Python"}],  # 대문자로 이미 존재
    )
    result = service.enrich_skill_tags(detail, ["Python"])
    python_count = sum(1 for t in result.skill_tags if t["text"].lower() == "python")
    assert python_count == 1


def test_enrich_skill_tags_word_boundary():
    service = JobService(engine=MagicMock())
    detail = JobDetail(
        job_id=1,
        requirements="Python3 경험, Java 개발자",
        preferred_points=None,
        skill_tags=[],
    )
    result = service.enrich_skill_tags(detail, ["Python", "Java"])
    texts = [t["text"] for t in result.skill_tags]
    assert "Python" not in texts  # "Python3"은 "Python"과 불일치
    assert "Java" in texts
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_job_service.py::test_add_keyword tests/test_job_service.py::test_add_keyword_duplicate tests/test_job_service.py::test_list_keywords tests/test_job_service.py::test_delete_keyword tests/test_job_service.py::test_delete_keyword_not_found tests/test_job_service.py::test_enrich_skill_tags_adds_matched_keywords tests/test_job_service.py::test_enrich_skill_tags_empty_keywords tests/test_job_service.py::test_enrich_skill_tags_no_duplicate tests/test_job_service.py::test_enrich_skill_tags_word_boundary -v
```

Expected: FAIL — `AttributeError` (메서드 미정의)

- [ ] **Step 3: `db/models/skill_keyword.py` 생성**

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime
from db.models.base import Base


class SkillKeyword(Base):
    __tablename__ = "skill_keywords"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: `db/models/__init__.py` 수정**

`SkillKeyword` import 및 `__all__` 추가:

```python
from db.models.base import Base
from db.models.job import Job
from db.models.application import Application
from db.models.job_detail import JobDetail
from db.models.search_preset import SearchPreset
from db.models.job_skip import JobSkip
from db.models.job_evaluation import JobEvaluation
from db.models.skill_keyword import SkillKeyword

__all__ = ["Base", "Job", "Application", "JobDetail", "SearchPreset", "JobSkip", "JobEvaluation", "SkillKeyword"]
```

- [ ] **Step 5: `db/repositories/skill_keyword_repository.py` 생성**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from db.models.skill_keyword import SkillKeyword


class SkillKeywordRepository:
    def __init__(self, session: Session):
        self.session = session

    def exists(self, keyword: str) -> bool:
        return self.session.scalars(
            select(SkillKeyword).where(SkillKeyword.keyword.ilike(keyword))
        ).first() is not None

    def add(self, keyword: str) -> bool:
        if self.exists(keyword):
            return False
        self.session.add(SkillKeyword(keyword=keyword))
        return True

    def find_all(self) -> list[str]:
        return list(self.session.scalars(
            select(SkillKeyword.keyword).order_by(SkillKeyword.keyword)
        ).all())

    def delete(self, keyword: str) -> SkillKeyword | None:
        obj = self.session.scalars(
            select(SkillKeyword).where(SkillKeyword.keyword.ilike(keyword))
        ).first()
        if obj:
            self.session.delete(obj)
        return obj
```

- [ ] **Step 6: `services/jobs/job_service.py` 수정**

파일 상단 import에 추가:

```python
import re
from db.repositories.skill_keyword_repository import SkillKeywordRepository
```

`JobService` 클래스 하단에 메서드 4개 추가:

```python
@transactional()
def add_keyword(self, keyword: str) -> str:
    keyword = keyword.strip()
    added = SkillKeywordRepository(get_current_session()).add(keyword)
    if not added:
        return f"이미 존재하는 키워드입니다: {keyword}"
    return f"키워드가 추가되었습니다: {keyword}"

@transactional()
def list_keywords(self) -> list[str]:
    return SkillKeywordRepository(get_current_session()).find_all()

@transactional()
def delete_keyword(self, keyword: str) -> str:
    deleted = SkillKeywordRepository(get_current_session()).delete(keyword)
    if not deleted:
        return f"존재하지 않는 키워드입니다: {keyword}"
    return f"키워드가 삭제되었습니다: {keyword}"

def enrich_skill_tags(self, job_detail: JobDetail, keywords: list[str]) -> JobDetail:
    if not keywords:
        return job_detail
    text = f"{job_detail.requirements or ''} {job_detail.preferred_points or ''}"
    existing = {t["text"].lower() for t in (job_detail.skill_tags or [])}
    new_tags = list(job_detail.skill_tags or [])
    for kw in keywords:
        if kw.lower() in existing:
            continue
        if re.search(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', text, re.IGNORECASE):
            new_tags.append({"text": kw})
            existing.add(kw.lower())
    job_detail.skill_tags = new_tags
    return job_detail
```

- [ ] **Step 7: 통과 확인**

```bash
pytest tests/test_job_service.py::test_add_keyword tests/test_job_service.py::test_add_keyword_duplicate tests/test_job_service.py::test_list_keywords tests/test_job_service.py::test_delete_keyword tests/test_job_service.py::test_delete_keyword_not_found tests/test_job_service.py::test_enrich_skill_tags_adds_matched_keywords tests/test_job_service.py::test_enrich_skill_tags_empty_keywords tests/test_job_service.py::test_enrich_skill_tags_no_duplicate tests/test_job_service.py::test_enrich_skill_tags_word_boundary -v
```

Expected: PASS (9개 모두)

- [ ] **Step 8: 전체 테스트 확인**

```bash
pytest -v
```

Expected: 기존 테스트 포함 전부 PASS

- [ ] **Step 9: 커밋**

```bash
git add db/models/skill_keyword.py db/models/__init__.py db/repositories/skill_keyword_repository.py services/jobs/job_service.py tests/test_job_service.py
git commit -m "feat: add SkillKeyword model, repository, and JobService keyword/enrich methods"
```

---

## Task 2: MCP 툴 3개 생성

**Files:**
- Create: `tools/add_skill_keyword.py`
- Create: `tools/list_skill_keywords.py`
- Create: `tools/delete_skill_keyword.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_tools.py` 하단에 추가:

```python
def test_add_skill_keyword_success():
    with patch("tools.add_skill_keyword.get_engine"), \
         patch("tools.add_skill_keyword.JobService") as MockService:
        mock_service = MagicMock()
        mock_service.add_keyword.return_value = "키워드가 추가되었습니다: Python"
        MockService.return_value = mock_service

        from tools.add_skill_keyword import add_skill_keyword
        result = add_skill_keyword("Python")

    assert result == "키워드가 추가되었습니다: Python"
    mock_service.add_keyword.assert_called_once_with("Python")


def test_list_skill_keywords_returns_markdown():
    with patch("tools.list_skill_keywords.get_engine"), \
         patch("tools.list_skill_keywords.JobService") as MockService:
        mock_service = MagicMock()
        mock_service.list_keywords.return_value = ["AWS", "Python"]
        MockService.return_value = mock_service

        from tools.list_skill_keywords import list_skill_keywords
        result = list_skill_keywords()

    assert "AWS" in result
    assert "Python" in result


def test_list_skill_keywords_empty():
    with patch("tools.list_skill_keywords.get_engine"), \
         patch("tools.list_skill_keywords.JobService") as MockService:
        mock_service = MagicMock()
        mock_service.list_keywords.return_value = []
        MockService.return_value = mock_service

        from tools.list_skill_keywords import list_skill_keywords
        result = list_skill_keywords()

    assert result == "등록된 키워드가 없습니다."


def test_delete_skill_keyword_success():
    with patch("tools.delete_skill_keyword.get_engine"), \
         patch("tools.delete_skill_keyword.JobService") as MockService:
        mock_service = MagicMock()
        mock_service.delete_keyword.return_value = "키워드가 삭제되었습니다: Python"
        MockService.return_value = mock_service

        from tools.delete_skill_keyword import delete_skill_keyword
        result = delete_skill_keyword("Python")

    assert result == "키워드가 삭제되었습니다: Python"
    mock_service.delete_keyword.assert_called_once_with("Python")
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_tools.py::test_add_skill_keyword_success tests/test_tools.py::test_list_skill_keywords_returns_markdown tests/test_tools.py::test_list_skill_keywords_empty tests/test_tools.py::test_delete_skill_keyword_success -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: `tools/add_skill_keyword.py` 생성**

```python
from db.connection import get_engine
from services.jobs.job_service import JobService


def add_skill_keyword(keyword: str) -> str:
    """스킬 키워드를 사전에 추가합니다."""
    return JobService(get_engine()).add_keyword(keyword)
```

- [ ] **Step 4: `tools/list_skill_keywords.py` 생성**

```python
from db.connection import get_engine
from services.jobs.job_service import JobService


def list_skill_keywords() -> str:
    """등록된 스킬 키워드 목록을 반환합니다."""
    keywords = JobService(get_engine()).list_keywords()
    if not keywords:
        return "등록된 키워드가 없습니다."
    lines = ["| 키워드 |", "|---|"]
    lines.extend(f"| {kw} |" for kw in keywords)
    lines.append(f"총 {len(keywords)}개")
    return "\n".join(lines)
```

- [ ] **Step 5: `tools/delete_skill_keyword.py` 생성**

```python
from db.connection import get_engine
from services.jobs.job_service import JobService


def delete_skill_keyword(keyword: str) -> str:
    """스킬 키워드를 사전에서 삭제합니다."""
    return JobService(get_engine()).delete_keyword(keyword)
```

- [ ] **Step 6: 통과 확인**

```bash
pytest tests/test_tools.py::test_add_skill_keyword_success tests/test_tools.py::test_list_skill_keywords_returns_markdown tests/test_tools.py::test_list_skill_keywords_empty tests/test_tools.py::test_delete_skill_keyword_success -v
```

Expected: PASS (4개 모두)

- [ ] **Step 7: 커밋**

```bash
git add tools/add_skill_keyword.py tools/list_skill_keywords.py tools/delete_skill_keyword.py tests/test_tools.py
git commit -m "feat: add add/list/delete_skill_keyword MCP tools"
```

---

## Task 3: sync_job_details 수정 + main.py 등록

**Files:**
- Modify: `tools/sync_job_details.py`
- Modify: `main.py`
- Test: `tests/test_tools.py`

기존 `test_sync_job_details_skips_failed_fetch`가 `enrich_skill_tags` 추가로 인해 깨집니다. 이 Task에서 함께 수정합니다.

- [ ] **Step 1: 기존 테스트 수정 + 새 테스트 추가**

`tests/test_tools.py`의 `test_sync_job_details_skips_failed_fetch` 수정 — `enrich_skill_tags`가 pass-through가 되도록:

```python
def test_sync_job_details_skips_failed_fetch():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.list_keywords.return_value = []
        mock_service.enrich_skill_tags.side_effect = lambda d, kw: d  # pass-through
        mock_service.upsert_job_details.return_value = "완료: 1개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [
            None,
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        result = sync_job_details()

    called_details = mock_service.upsert_job_details.call_args[0][0]
    assert len(called_details) == 1
    assert called_details[0].job_id == 102
```

`tests/test_tools.py` 하단에 새 테스트 추가:

```python
def test_sync_job_details_calls_enrich_for_each_detail():
    detail_101 = JobDetail(job_id=101, requirements="Python 경험", preferred_points=None, skill_tags=[])
    detail_102 = JobDetail(job_id=102, requirements="Java 경험", preferred_points=None, skill_tags=[])

    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.list_keywords.return_value = ["Python", "Java"]
        mock_service.enrich_skill_tags.side_effect = lambda d, kw: d
        mock_service.upsert_job_details.return_value = "완료: 2개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [detail_101, detail_102]
        MockClient.return_value = mock_client

        sync_job_details()

    mock_service.list_keywords.assert_called_once()
    assert mock_service.enrich_skill_tags.call_count == 2
    mock_service.enrich_skill_tags.assert_any_call(detail_101, ["Python", "Java"])
    mock_service.enrich_skill_tags.assert_any_call(detail_102, ["Python", "Java"])
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_tools.py::test_sync_job_details_skips_failed_fetch tests/test_tools.py::test_sync_job_details_calls_enrich_for_each_detail -v
```

Expected: `test_sync_job_details_calls_enrich_for_each_detail` FAIL (`list_keywords` 호출 없음), `test_sync_job_details_skips_failed_fetch` PASS (sync_job_details.py 미수정 상태에서도 통과)

- [ ] **Step 3: `tools/sync_job_details.py` 수정**

```python
import time

from constants import CRAWL_DELAY_SECONDS
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.wanted.wanted_client import WantedClient


def sync_job_details(
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """미수집 공고의 상세 정보를 Wanted API에서 가져와 저장합니다."""
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    target_ids = service.get_jobs_without_details(job_ids=job_ids, limit=limit)
    if not target_ids:
        return "처리할 공고가 없습니다."

    fetched = []
    for i, job_id in enumerate(target_ids):
        if i > 0:
            time.sleep(CRAWL_DELAY_SECONDS)
        detail = client.fetch_job_detail(job_id)
        if detail is None:
            continue
        fetched.append(detail)

    if not fetched:
        return "상세 정보를 가져온 공고가 없습니다."

    keywords = service.list_keywords()
    fetched = [service.enrich_skill_tags(d, keywords) for d in fetched]

    return service.upsert_job_details(fetched)
```

- [ ] **Step 4: `main.py` 수정**

import 3개 추가:

```python
from tools.add_skill_keyword import add_skill_keyword
from tools.list_skill_keywords import list_skill_keywords
from tools.delete_skill_keyword import delete_skill_keyword
```

툴 등록 3개 추가 (기존 `mcp.tool()(save_job_evaluations)` 다음):

```python
mcp.tool()(add_skill_keyword)
mcp.tool()(list_skill_keywords)
mcp.tool()(delete_skill_keyword)
```

- [ ] **Step 5: 통과 확인**

```bash
pytest tests/test_tools.py::test_sync_job_details_skips_failed_fetch tests/test_tools.py::test_sync_job_details_calls_enrich_for_each_detail -v
```

Expected: PASS (2개 모두)

- [ ] **Step 6: 전체 테스트 확인**

```bash
pytest -v
```

Expected: 전부 PASS

- [ ] **Step 7: 커밋**

```bash
git add tools/sync_job_details.py main.py tests/test_tools.py
git commit -m "feat: enrich skill_tags during sync_job_details, register keyword tools in main"
```
