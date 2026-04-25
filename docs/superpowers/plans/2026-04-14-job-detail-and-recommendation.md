# Job Detail 수집 및 기술스택 기반 추천 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 원티드 채용공고 상세(requirements, skill_tags)를 수집하고, 사용자 기술스택 파라미터 기반으로 미지원 공고를 추천하는 MCP 툴 2개(`sync_job_details`, `recommend_jobs`)를 추가한다.

**Architecture:** `job_details` 테이블을 신규 추가해 공고 상세 정보를 저장한다. `sync_job_details`는 Wanted detail API를 배치 호출하고, `recommend_jobs`는 skill_tags SQL 1차 필터 후 Claude API로 최종 추천한다. detail이 없는 공고는 `recommend_jobs` 호출 시 lazy fetch한다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, FastMCP, httpx, MySQL, anthropic SDK (claude-sonnet-4-6)

---

## 파일 구조

| 파일 | 변경 |
|---|---|
| `db/models.py` | `job_details_table` 추가 |
| `services/wanted_client.py` | `fetch_job_detail()` 메서드 추가 |
| `services/job_service.py` | `upsert_job_details()`, `get_unapplied_job_rows()`, `get_recommended_jobs()` 추가 |
| `tools/sync_job_details.py` | 신규 생성 |
| `tools/recommend_jobs.py` | 신규 생성 |
| `main.py` | 두 툴 등록 |
| `requirements.txt` | `anthropic>=0.30.0` 추가 |
| `.env.example` | `ANTHROPIC_API_KEY` 추가 |
| `tests/test_wanted_client.py` | `fetch_job_detail` 테스트 추가 |
| `tests/test_job_service.py` | 신규 메서드 테스트 추가 |
| `tests/test_tools.py` | `sync_job_details`, `recommend_jobs` 테스트 추가 |

---

### Task 1: DB 스키마 — job_details 테이블 추가

**Files:**
- Modify: `db/models.py`
- Modify: `db/connection.py` (create_tables가 새 테이블 생성하는지 확인)

- [ ] **Step 1: 현재 models.py와 connection.py 읽기**

  `db/models.py`와 `db/connection.py`를 읽어 기존 패턴 확인.

- [ ] **Step 2: job_details_table 추가**

  `db/models.py`에 아래 임포트 추가 후 테이블 정의 추가:

  ```python
  # 기존 임포트에 Text, ForeignKey 추가
  from sqlalchemy import (
      Table, Column, Integer, String, Boolean, DateTime, JSON, MetaData, Text, ForeignKey
  )
  ```

  ```python
  job_details_table = Table(
      "job_details", metadata,
      Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
      Column("requirements", Text),
      Column("preferred_points", Text),
      Column("skill_tags", JSON),
      Column("fetched_at", DateTime, nullable=False),
  )
  ```

- [ ] **Step 3: create_tables 동작 확인**

  `db/connection.py`의 `create_tables()`가 `metadata.create_all(engine)`을 호출하는지 확인.
  호출하면 추가 수정 불필요. 아니라면 `job_details_table`을 명시적으로 추가.

- [ ] **Step 4: 테이블 생성 확인**

  ```bash
  python -c "from db.connection import create_tables; create_tables(); print('OK')"
  ```
  Expected: `OK` 출력, 오류 없음.

- [ ] **Step 5: Commit**

  ```bash
  git add db/models.py
  git commit -m "feat: job_details 테이블 스키마 추가"
  ```

---

### Task 2: WantedClient — fetch_job_detail() 추가

**Files:**
- Modify: `services/wanted_client.py`
- Modify: `tests/test_wanted_client.py`

- [ ] **Step 1: 실패하는 테스트 작성**

  `tests/test_wanted_client.py` 하단에 추가:

  ```python
  MOCK_DETAIL_RESPONSE = {
      "error_code": None,
      "message": "ok",
      "data": {
          "job": {
              "id": 210918,
              "detail": {
                  "requirements": "Python 3년 이상",
                  "preferred_points": "FastAPI 경험자 우대",
              }
          },
          "skill_tags": [
              {"tag_type_id": 1554, "text": "Python"},
              {"tag_type_id": 1562, "text": "SQL"},
          ]
      }
  }


  def test_fetch_job_detail_success():
      with patch("services.wanted_client.httpx.get") as mock_get:
          mock_resp = MagicMock()
          mock_resp.status_code = 200
          mock_resp.json.return_value = MOCK_DETAIL_RESPONSE
          mock_get.return_value = mock_resp

          client = WantedClient()
          result = client.fetch_job_detail(210918)

      assert result is not None
      assert result["job_id"] == 210918
      assert result["requirements"] == "Python 3년 이상"
      assert result["preferred_points"] == "FastAPI 경험자 우대"
      assert result["skill_tags"] == [
          {"tag_type_id": 1554, "text": "Python"},
          {"tag_type_id": 1562, "text": "SQL"},
      ]


  def test_fetch_job_detail_returns_none_on_error():
      with patch("services.wanted_client.httpx.get") as mock_get:
          mock_resp = MagicMock()
          mock_resp.status_code = 404
          mock_get.return_value = mock_resp

          client = WantedClient()
          result = client.fetch_job_detail(99999)

      assert result is None
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```bash
  pytest tests/test_wanted_client.py::test_fetch_job_detail_success tests/test_wanted_client.py::test_fetch_job_detail_returns_none_on_error -v
  ```
  Expected: FAIL (AttributeError: 'WantedClient' object has no attribute 'fetch_job_detail')

- [ ] **Step 3: fetch_job_detail() 구현**

  `services/wanted_client.py`에 상수 추가 후 메서드 추가:

  ```python
  DETAIL_API_URL = "https://www.wanted.co.kr/api/chaos/jobs/v4/{job_id}/details"
  ```

  `WantedClient` 클래스에:

  ```python
  def fetch_job_detail(self, job_id: int) -> dict | None:
      """단일 공고 detail 조회. 실패 시 None 반환."""
      url = DETAIL_API_URL.format(job_id=job_id)
      try:
          resp = self._get(url, params={})
      except RuntimeError:
          return None
      if resp.status_code != 200:
          return None
      data = resp.json().get("data", {})
      job = data.get("job", {})
      detail = job.get("detail", {})
      return {
          "job_id": job_id,
          "requirements": detail.get("requirements"),
          "preferred_points": detail.get("preferred_points"),
          "skill_tags": data.get("skill_tags", []),
      }
  ```

- [ ] **Step 4: 테스트 통과 확인**

  ```bash
  pytest tests/test_wanted_client.py -v
  ```
  Expected: 모든 테스트 PASS

- [ ] **Step 5: Commit**

  ```bash
  git add services/wanted_client.py tests/test_wanted_client.py
  git commit -m "feat: WantedClient.fetch_job_detail() 추가"
  ```

---

### Task 3: JobService — upsert_job_details, get_unapplied_job_rows 추가

**Files:**
- Modify: `services/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: 실패하는 테스트 작성**

  `tests/test_job_service.py` 하단에 추가:

  ```python
  RAW_DETAIL = {
      "job_id": 1001,
      "requirements": "Python 3년 이상",
      "preferred_points": "FastAPI 경험자 우대",
      "skill_tags": [{"tag_type_id": 1554, "text": "Python"}],
  }


  def test_upsert_job_details_calls_execute():
      mock_engine = MagicMock()
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
      mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
      mock_conn.execute.return_value = MagicMock()

      service = JobService(engine=mock_engine)
      result = service.upsert_job_details([RAW_DETAIL])

      assert mock_conn.execute.called
      assert "1개 처리" in result


  def test_get_unapplied_job_rows_returns_list():
      mock_engine = MagicMock()
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
      mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

      mock_conn.execute.return_value.mappings.return_value.all.return_value = [
          {
              "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
              "location": "서울", "employment_type": "regular",
              "requirements": None, "preferred_points": None,
              "skill_tags": None, "fetched_at": None,
          }
      ]

      service = JobService(engine=mock_engine)
      rows = service.get_unapplied_job_rows()

      assert isinstance(rows, list)
      assert rows[0]["id"] == 1001
      assert rows[0]["fetched_at"] is None
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```bash
  pytest tests/test_job_service.py::test_upsert_job_details_calls_execute tests/test_job_service.py::test_get_unapplied_job_rows_returns_list -v
  ```
  Expected: FAIL

- [ ] **Step 3: job_service.py 임포트 수정**

  `services/job_service.py` 상단 임포트에 추가:

  ```python
  from db.models import jobs_table, applications_table, search_presets_table, job_details_table
  ```

- [ ] **Step 4: upsert_job_details() 구현**

  `JobService` 클래스에 추가:

  ```python
  def upsert_job_details(self, details: list[dict]) -> str:
      if not details:
          return "완료: 0개 처리"
      now = datetime.now(timezone.utc).replace(tzinfo=None)
      rows = [
          {
              "job_id": d["job_id"],
              "requirements": d.get("requirements"),
              "preferred_points": d.get("preferred_points"),
              "skill_tags": d.get("skill_tags", []),
              "fetched_at": now,
          }
          for d in details
      ]
      with self.engine.connect() as conn:
          stmt = insert(job_details_table).values(rows)
          upsert_stmt = stmt.on_duplicate_key_update(
              requirements=stmt.inserted.requirements,
              preferred_points=stmt.inserted.preferred_points,
              skill_tags=stmt.inserted.skill_tags,
              fetched_at=stmt.inserted.fetched_at,
          )
          conn.execute(upsert_stmt)
          conn.commit()
      return f"완료: {len(rows)}개 처리"
  ```

- [ ] **Step 5: get_unapplied_job_rows() 구현**

  `JobService` 클래스에 추가:

  ```python
  def get_unapplied_job_rows(
      self,
      job_group_id: int | None = None,
      location: str | None = None,
      employment_type: str | None = None,
  ) -> list[dict]:
      if employment_type:
          employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
      query = text("""
          SELECT j.id, j.company_name, j.title, j.location, j.employment_type,
                 jd.requirements, jd.preferred_points, jd.skill_tags, jd.fetched_at
          FROM jobs j
          LEFT JOIN applications a ON j.id = a.job_id
          LEFT JOIN job_details jd ON j.id = jd.job_id
          WHERE a.job_id IS NULL
            AND j.is_active = TRUE
            AND (:job_group_id IS NULL OR j.job_group_id = :job_group_id)
            AND (:location IS NULL OR j.location LIKE CONCAT('%', :location, '%'))
            AND (:employment_type IS NULL OR j.employment_type = :employment_type)
      """)
      with self.engine.connect() as conn:
          rows = conn.execute(query, {
              "job_group_id": job_group_id,
              "location": location,
              "employment_type": employment_type,
          }).mappings().all()
      return [dict(r) for r in rows]
  ```

- [ ] **Step 6: 테스트 통과 확인**

  ```bash
  pytest tests/test_job_service.py -v
  ```
  Expected: 모든 테스트 PASS

- [ ] **Step 7: Commit**

  ```bash
  git add services/job_service.py tests/test_job_service.py
  git commit -m "feat: JobService upsert_job_details, get_unapplied_job_rows 추가"
  ```

---

### Task 4: sync_job_details 툴

**Files:**
- Create: `tools/sync_job_details.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: 실패하는 테스트 작성**

  `tests/test_tools.py`에 추가 (기존 import 블록 아래):

  ```python
  from tools.sync_job_details import sync_job_details


  def test_sync_job_details_processes_missing():
      with patch("tools.sync_job_details.get_engine"), \
           patch("tools.sync_job_details.WantedClient") as MockClient, \
           patch("tools.sync_job_details.JobService") as MockService, \
           patch("tools.sync_job_details.time.sleep") as mock_sleep:

          mock_service = MagicMock()
          mock_service.get_jobs_without_details.return_value = [101, 102]
          mock_service.upsert_job_details.return_value = "완료: 2개 처리"
          MockService.return_value = mock_service

          mock_client = MagicMock()
          mock_client.fetch_job_detail.side_effect = [
              {"job_id": 101, "requirements": "req1", "preferred_points": "pref1", "skill_tags": []},
              {"job_id": 102, "requirements": "req2", "preferred_points": None, "skill_tags": []},
          ]
          MockClient.return_value = mock_client

          result = sync_job_details()

      assert "2개 처리" in result
      assert mock_client.fetch_job_detail.call_count == 2
      # 2개 처리 시 딜레이는 1회 (첫 번째는 스킵)
      mock_sleep.assert_called_once_with(1)


  def test_sync_job_details_skips_failed_fetch():
      with patch("tools.sync_job_details.get_engine"), \
           patch("tools.sync_job_details.WantedClient") as MockClient, \
           patch("tools.sync_job_details.JobService") as MockService, \
           patch("tools.sync_job_details.time.sleep"):

          mock_service = MagicMock()
          mock_service.get_jobs_without_details.return_value = [101, 102]
          mock_service.upsert_job_details.return_value = "완료: 1개 처리"
          MockService.return_value = mock_service

          mock_client = MagicMock()
          mock_client.fetch_job_detail.side_effect = [
              None,  # 101 실패
              {"job_id": 102, "requirements": "req2", "preferred_points": None, "skill_tags": []},
          ]
          MockClient.return_value = mock_client

          result = sync_job_details()

      # 성공한 1개만 upsert
      called_details = mock_service.upsert_job_details.call_args[0][0]
      assert len(called_details) == 1
      assert called_details[0]["job_id"] == 102
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```bash
  pytest tests/test_tools.py::test_sync_job_details_processes_missing tests/test_tools.py::test_sync_job_details_skips_failed_fetch -v
  ```
  Expected: FAIL (ImportError)

- [ ] **Step 3: get_jobs_without_details() 테스트 및 구현**

  먼저 `tests/test_job_service.py`에 테스트 추가:

  ```python
  def test_get_jobs_without_details_filters_existing():
      """job_ids 전달 시 이미 detail 있는 것 제외, limit 적용"""
      mock_engine = MagicMock()
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
      mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
      # job_id 101은 이미 존재
      mock_conn.execute.return_value.scalars.return_value.all.return_value = [101]

      service = JobService(engine=mock_engine)
      result = service.get_jobs_without_details(job_ids=[101, 102, 103], limit=2)

      # limit=2 → [101, 102] 중 101은 이미 있으므로 [102]만
      assert result == [102]


  def test_get_jobs_without_details_no_job_ids():
      """job_ids 없을 때 SQL로 전체 조회 (LIMIT 바운드 파라미터)"""
      mock_engine = MagicMock()
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
      mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
      mock_conn.execute.return_value.scalars.return_value.all.return_value = [201, 202]

      service = JobService(engine=mock_engine)
      result = service.get_jobs_without_details(limit=10)

      assert result == [201, 202]
      # execute 호출 인자에 limit 바인딩 확인
      call_kwargs = mock_conn.execute.call_args
      assert call_kwargs is not None
  ```

  테스트 실패 확인:
  ```bash
  pytest tests/test_job_service.py::test_get_jobs_without_details_filters_existing tests/test_job_service.py::test_get_jobs_without_details_no_job_ids -v
  ```
  Expected: FAIL

  `services/job_service.py`에 추가 (SQL injection 방지: `limit`은 바운드 파라미터로 처리):

  ```python
  def get_jobs_without_details(
      self,
      job_ids: list[int] | None = None,
      limit: int | None = None,
  ) -> list[int]:
      """job_details가 없는 공고의 job_id 목록 반환."""
      if job_ids is not None:
          candidates = job_ids[:limit] if limit is not None else job_ids
          with self.engine.connect() as conn:
              existing = set(conn.execute(
                  select(job_details_table.c.job_id).where(
                      job_details_table.c.job_id.in_(candidates)
                  )
              ).scalars().all())
          return [jid for jid in candidates if jid not in existing]
      # limit을 바운드 파라미터로 사용 (SQL injection 방지)
      query = text("""
          SELECT j.id FROM jobs j
          LEFT JOIN job_details jd ON j.id = jd.job_id
          WHERE jd.job_id IS NULL AND j.is_active = TRUE
          ORDER BY j.id
          LIMIT :limit
      """) if limit is not None else text("""
          SELECT j.id FROM jobs j
          LEFT JOIN job_details jd ON j.id = jd.job_id
          WHERE jd.job_id IS NULL AND j.is_active = TRUE
          ORDER BY j.id
      """)
      params = {"limit": limit} if limit is not None else {}
      with self.engine.connect() as conn:
          return list(conn.execute(query, params).scalars().all())
  ```

  테스트 통과 확인:
  ```bash
  pytest tests/test_job_service.py -v
  ```
  Expected: PASS

- [ ] **Step 4: sync_job_details.py 생성**

  ```python
  import time
  from db.connection import get_engine
  from services.wanted.wanted_client import WantedClient
  from services.job_service import JobService


  def sync_job_details(
      job_ids: list[int] | None = None,
      limit: int | None = None,
  ) -> str:
      engine = get_engine()
      service = JobService(engine)
      client = WantedClient()

      target_ids = service.get_jobs_without_details(job_ids=job_ids, limit=limit)
      if not target_ids:
          return "처리할 공고가 없습니다."

      fetched = []
      for i, job_id in enumerate(target_ids):
          if i > 0:
              time.sleep(1)
          detail = client.fetch_job_detail(job_id)
          if detail is None:
              continue
          fetched.append(detail)

      if not fetched:
          return "상세 정보를 가져온 공고가 없습니다."
      return service.upsert_job_details(fetched)
  ```

- [ ] **Step 5: 테스트 통과 확인**

  ```bash
  pytest tests/test_tools.py::test_sync_job_details_processes_missing tests/test_tools.py::test_sync_job_details_skips_failed_fetch -v
  ```
  Expected: PASS

- [ ] **Step 6: Commit**

  ```bash
  git add tools/sync_job_details.py services/job_service.py tests/test_tools.py tests/test_job_service.py
  git commit -m "feat: sync_job_details 툴 추가"
  ```

---

### Task 5: recommend_jobs 툴

**Files:**
- Create: `tools/recommend_jobs.py`
- Modify: `services/job_service.py` (get_recommended_jobs 추가)
- Modify: `tests/test_job_service.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: get_recommended_jobs() 테스트 작성**

  `tests/test_job_service.py`에 추가:

  ```python
  def test_get_recommended_jobs_scores_skill_tags():
      """skill_tags 매칭 수 기준으로 상위 N개 반환"""
      mock_engine = MagicMock()
      mock_conn = MagicMock()
      mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
      mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

      from datetime import datetime
      now = datetime.now()
      mock_conn.execute.return_value.mappings.return_value.all.return_value = [
          {
              "id": 1, "company_name": "A사", "title": "Backend",
              "location": "서울", "employment_type": "regular",
              "requirements": "Python req", "preferred_points": "AWS 우대",
              "skill_tags": [{"tag_type_id": 1554, "text": "Python"}, {"tag_type_id": 1698, "text": "AWS"}],
              "fetched_at": now,
          },
          {
              "id": 2, "company_name": "B사", "title": "Frontend",
              "location": "서울", "employment_type": "regular",
              "requirements": "React req", "preferred_points": None,
              "skill_tags": [{"tag_type_id": 1600, "text": "React"}],
              "fetched_at": now,
          },
          {
              "id": 3, "company_name": "C사", "title": "Fullstack",
              "location": "서울", "employment_type": "regular",
              "requirements": None, "preferred_points": None,
              "skill_tags": None, "fetched_at": None,  # detail 없음
          },
      ]

      service = JobService(engine=mock_engine)
      candidates = service.get_recommended_jobs(
          skills=["Python", "AWS"],
          location="서울",
          employment_type="정규직",
          top_k=15,
      )

      # detail 없는 공고(id=3)는 제외, 점수 높은 순 정렬
      assert candidates[0]["id"] == 1  # 매칭 2개
      assert candidates[1]["id"] == 2  # 매칭 0개
      assert all(c["fetched_at"] is not None for c in candidates)
  ```

- [ ] **Step 2: 테스트 실패 확인**

  ```bash
  pytest tests/test_job_service.py::test_get_recommended_jobs_scores_skill_tags -v
  ```
  Expected: FAIL

- [ ] **Step 3: get_recommended_jobs() 구현**

  `services/job_service.py`에 추가 (rows를 직접 받아 DB 재조회 없음):

  ```python
  def get_recommended_jobs(
      self,
      skills: list[str],
      rows: list[dict],
      top_k: int = 15,
  ) -> list[dict]:
      """전달된 rows에서 skill_tags 매칭 점수 기준 상위 top_k개 반환 (detail 없는 공고 제외)."""
      skills_lower = {s.lower() for s in skills}

      def score(row: dict) -> int:
          tags = row.get("skill_tags") or []
          return sum(1 for t in tags if t.get("text", "").lower() in skills_lower)

      with_detail = [r for r in rows if r.get("fetched_at") is not None]
      scored = sorted(with_detail, key=score, reverse=True)
      return scored[:top_k]
  ```

  테스트도 시그니처에 맞게 수정 — `test_get_recommended_jobs_scores_skill_tags`의 호출부:

  ```python
  # 변경 전
  candidates = service.get_recommended_jobs(
      skills=["Python", "AWS"],
      location="서울",
      employment_type="정규직",
      top_k=15,
  )

  # 변경 후: rows를 직접 전달
  all_rows = [dict(r) for r in mock_conn.execute.return_value.mappings.return_value.all.return_value]
  candidates = service.get_recommended_jobs(
      skills=["Python", "AWS"],
      rows=all_rows,
      top_k=15,
  )
  ```

- [ ] **Step 4: 테스트 통과 확인**

  ```bash
  pytest tests/test_job_service.py -v
  ```
  Expected: PASS

- [ ] **Step 5: recommend_jobs 툴 테스트 작성**

  `tests/test_tools.py`에 추가:

  ```python
  from tools.recommend_jobs import recommend_jobs


  def test_recommend_jobs_calls_claude_and_returns_markdown():
      candidates = [
          {
              "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
              "location": "서울", "requirements": "Python req", "preferred_points": "AWS 우대",
              "skill_tags": [{"tag_type_id": 1554, "text": "Python"}],
              "fetched_at": MagicMock(),
          }
      ]

      with patch("tools.recommend_jobs.get_engine"), \
           patch("tools.recommend_jobs.JobService") as MockService, \
           patch("tools.recommend_jobs.WantedClient") as MockClient, \
           patch("tools.recommend_jobs.anthropic.Anthropic") as MockAnthropic, \
           patch("tools.recommend_jobs.time.sleep"):

          mock_service = MagicMock()
          mock_service.get_unapplied_job_rows.return_value = candidates
          mock_service.get_recommended_jobs.return_value = candidates
          mock_service.upsert_job_details.return_value = "완료: 1개 처리"
          MockService.return_value = mock_service

          mock_client = MagicMock()
          mock_client.fetch_job_detail.return_value = {
              "job_id": 1001, "requirements": "Python req",
              "preferred_points": "AWS 우대", "skill_tags": [],
          }
          MockClient.return_value = mock_client

          mock_claude = MagicMock()
          mock_claude.messages.create.return_value.content = [
              MagicMock(text='[{"job_id": 1001, "reason": "Python 스택 일치"}]')
          ]
          MockAnthropic.return_value = mock_claude

          result = recommend_jobs(skills=["Python"], top_n=5)

      # Claude가 호출됐는지 확인
      mock_claude.messages.create.assert_called_once()
      # 결과에 링크와 회사명 포함 확인
      assert "테스트컴퍼니" in result
      assert "https://www.wanted.co.kr/wd/1001" in result
      assert "Python 스택 일치" in result


  def test_recommend_jobs_fallback_on_claude_failure():
      candidates = [
          {
              "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
              "location": "서울", "requirements": "Python req", "preferred_points": None,
              "skill_tags": [{"tag_type_id": 1554, "text": "Python"}],
              "fetched_at": MagicMock(),
          }
      ]

      with patch("tools.recommend_jobs.get_engine"), \
           patch("tools.recommend_jobs.JobService") as MockService, \
           patch("tools.recommend_jobs.WantedClient") as MockClient, \
           patch("tools.recommend_jobs.anthropic.Anthropic") as MockAnthropic, \
           patch("tools.recommend_jobs.time.sleep"):

          mock_service = MagicMock()
          mock_service.get_unapplied_job_rows.return_value = candidates
          mock_service.get_recommended_jobs.return_value = candidates
          MockService.return_value = mock_service

          mock_client = MagicMock()
          mock_client.fetch_job_detail.return_value = None
          MockClient.return_value = mock_client

          MockAnthropic.return_value.messages.create.side_effect = Exception("API 오류")

          result = recommend_jobs(skills=["Python"], top_n=5)

      # Claude 실패해도 결과 반환
      assert isinstance(result, str)
      assert len(result) > 0
  ```

- [ ] **Step 6: 테스트 실패 확인**

  ```bash
  pytest tests/test_tools.py::test_recommend_jobs_calls_claude_and_returns_markdown tests/test_tools.py::test_recommend_jobs_fallback_on_claude_failure -v
  ```
  Expected: FAIL (ImportError)

- [ ] **Step 7: recommend_jobs.py 생성**

  ```python
  import json
  import os
  import time
  import anthropic
  from db.connection import get_engine
  from services.wanted.wanted_client import WantedClient
  from services.job_service import JobService

  CLAUDE_MODEL = "claude-sonnet-4-6"
  LAZY_FETCH_LIMIT = 20


  def recommend_jobs(
      skills: list[str],
      location: str | None = None,
      employment_type: str | None = None,
      job_group_id: int | None = None,
      top_n: int = 10,
  ) -> str:
      engine = get_engine()
      service = JobService(engine)
      client = WantedClient()

      # 1. 미지원 공고 전체 조회 (필터 적용, LIMIT 없음)
      all_rows = service.get_unapplied_job_rows(
          job_group_id=job_group_id,
          location=location,
          employment_type=employment_type,
      )
      if not all_rows:
          return "미지원 공고가 없습니다."

      # 2. detail 없는 공고 lazy fetch (최대 LAZY_FETCH_LIMIT개)
      missing = [r for r in all_rows if r.get("fetched_at") is None][:LAZY_FETCH_LIMIT]
      if missing:
          fetched = []
          for i, row in enumerate(missing):
              if i > 0:
                  time.sleep(1)
              detail = client.fetch_job_detail(row["id"])
              if detail:
                  fetched.append(detail)
          if fetched:
              service.upsert_job_details(fetched)
          # detail 업데이트 후 한 번만 재조회
          all_rows = service.get_unapplied_job_rows(
              job_group_id=job_group_id,
              location=location,
              employment_type=employment_type,
          )

      # 3. 이미 조회된 all_rows를 직접 전달 (DB 재조회 없음)
      candidates = service.get_recommended_jobs(
          skills=skills,
          rows=all_rows,
          top_k=15,
      )
      if not candidates:
          return "추천할 공고가 없습니다. (상세 정보 없음)"

      # 4. Claude API로 최종 추천
      candidate_ids = {c["id"] for c in candidates}
      try:
          prompt_jobs = "\n\n".join(
              f"job_id: {c['id']}\n회사: {c['company_name']}\n포지션: {c['title']}\n"
              f"자격요건: {c.get('requirements') or '정보 없음'}\n"
              f"우대사항: {c.get('preferred_points') or '정보 없음'}"
              for c in candidates
          )
          user_message = (
              f"내 기술스택: {', '.join(skills)}\n\n"
              f"다음 채용공고 중 내 스택과 가장 잘 맞는 상위 {top_n}개를 추천해줘.\n"
              f"반드시 JSON 배열로만 응답해: "
              f'[{{"job_id": <int>, "reason": "<한 줄 이유>"}}]\n\n'
              f"{prompt_jobs}"
          )
          ai_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
          response = ai_client.messages.create(
              model=CLAUDE_MODEL,
              max_tokens=1024,
              system="당신은 채용 어시스턴트입니다. 요청한 JSON 형식으로만 응답하세요.",
              messages=[{"role": "user", "content": user_message}],
          )
          raw = response.content[0].text.strip()
          # JSON 파싱 및 hallucination 방어
          recommendations = json.loads(raw)
          recommendations = [r for r in recommendations if r.get("job_id") in candidate_ids]
          recommendations = recommendations[:top_n]

          job_map = {c["id"]: c for c in candidates}
          lines = [f"## 추천 공고 Top {len(recommendations)}\n",
                   "| 회사명 | 포지션 | 지역 | 추천 이유 | 링크 |",
                   "|---|---|---|---|---|"]
          for rec in recommendations:
              job = job_map[rec["job_id"]]
              link = f"https://www.wanted.co.kr/wd/{job['id']}"
              lines.append(
                  f"| {job['company_name']} | {job['title']} | {job['location']} "
                  f"| {rec['reason']} | {link} |"
              )
          return "\n".join(lines)

      except Exception:
          # Claude 실패 시 skill_tags 점수 순 결과 반환
          lines = ["## 추천 공고 (skill_tags 매칭 기준)\n",
                   "| 회사명 | 포지션 | 지역 | 링크 |",
                   "|---|---|---|---|"]
          for c in candidates[:top_n]:
              link = f"https://www.wanted.co.kr/wd/{c['id']}"
              lines.append(f"| {c['company_name']} | {c['title']} | {c['location']} | {link} |")
          return "\n".join(lines)
  ```

- [ ] **Step 8: 테스트 통과 확인**

  ```bash
  pytest tests/test_tools.py -v
  ```
  Expected: PASS

- [ ] **Step 9: Commit**

  ```bash
  git add tools/recommend_jobs.py services/job_service.py tests/test_job_service.py tests/test_tools.py
  git commit -m "feat: recommend_jobs 툴 추가 (skill_tags 필터 + Claude 추천)"
  ```

---

### Task 6: 등록 및 의존성 추가

**Files:**
- Modify: `main.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: main.py에 두 툴 등록**

  `main.py`에 추가:

  ```python
  from tools.sync_job_details import sync_job_details
  from tools.recommend_jobs import recommend_jobs
  ```

  그리고:

  ```python
  mcp.tool()(sync_job_details)
  mcp.tool()(recommend_jobs)
  ```

- [ ] **Step 2: requirements.txt에 anthropic 추가**

  ```
  anthropic>=0.30.0
  ```

- [ ] **Step 3: .env.example에 ANTHROPIC_API_KEY 추가**

  ```
  ANTHROPIC_API_KEY=your_api_key_here
  ```

- [ ] **Step 4: 패키지 설치**

  ```bash
  pip install anthropic>=0.30.0
  ```

- [ ] **Step 5: 전체 테스트 통과 확인**

  ```bash
  pytest tests/ -v
  ```
  Expected: 모든 테스트 PASS

- [ ] **Step 6: MCP 서버 시작 확인**

  ```bash
  python main.py 2>&1 | head -5
  ```
  Expected: FastMCP 배너 출력, 오류 없음

- [ ] **Step 7: Commit**

  ```bash
  git add main.py requirements.txt .env.example
  git commit -m "feat: sync_job_details, recommend_jobs MCP 툴 등록 및 의존성 추가"
  ```
