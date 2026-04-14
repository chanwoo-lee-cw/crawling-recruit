import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from services.job_service import JobService


RAW_JOB = {
    "id": 1001,
    "company": {"id": 10, "name": "테스트컴퍼니"},
    "position": "Backend Engineer",
    "address": {"location": "서울"},
    "employment_type": "regular",
    "annual_from": 0,
    "annual_to": 100,
    "job_group_id": 518,
    "category_tag": {"parent_id": 518, "id": 872},
    "create_time": "2026-01-01T00:00:00",
}

RAW_APP = {
    "id": 9001,
    "job_id": 2001,
    "status": "complete",
    "apply_time": "2026-01-01T00:00:00",
}


def test_parse_job_row():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_JOB)
    assert row["id"] == 1001
    assert row["company_name"] == "테스트컴퍼니"
    assert row["title"] == "Backend Engineer"
    assert row["location"] == "서울"
    assert row["employment_type"] == "regular"
    assert row["job_group_id"] == 518
    assert row["category_tag_id"] == 872
    assert row["is_active"] is True


def test_parse_application_row():
    service = JobService(engine=MagicMock())
    row = service._parse_application(RAW_APP)
    assert row["id"] == 9001
    assert row["job_id"] == 2001
    assert row["status"] == "complete"


def test_upsert_jobs_calls_execute():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    # First execute() is the pre-query for existing IDs → returns empty (all new)
    pre_query_result = MagicMock()
    pre_query_result.scalars.return_value.all.return_value = []
    # Second execute() is the upsert → rowcount=1
    upsert_result = MagicMock()
    upsert_result.rowcount = 1
    mock_conn.execute.side_effect = [pre_query_result, upsert_result]

    service = JobService(engine=mock_engine)
    result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_conn.execute.call_count == 2
    assert "동기화 완료: 신규 1개, 변경 0개, 유지 0개" == result


def test_save_preset_invalid_key():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError, match="유효하지 않은 파라미터 키"):
        service.save_preset("테스트", {"invalid_key": 1})


def test_save_preset_valid():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    service = JobService(engine=mock_engine)
    result = service.save_preset("백엔드 신입 서울", {"job_group_id": 518, "locations": "서울"})

    assert "저장 완료" in result


def test_get_unapplied_jobs_returns_markdown():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    mock_conn.execute.return_value.mappings.return_value.all.return_value = [
        {"id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
    ]

    service = JobService(engine=mock_engine)
    result = service.get_unapplied_jobs()

    assert "| 회사명 |" in result
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


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
    call_kwargs = mock_conn.execute.call_args
    assert call_kwargs is not None


def test_get_recommended_jobs_scores_skill_tags():
    """skill_tags 매칭 수 기준으로 상위 N개 반환, detail 없는 공고 제외"""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    from datetime import datetime
    now = datetime.now()
    all_rows = [
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
        rows=all_rows,
        top_k=15,
    )

    # detail 없는 공고(id=3)는 제외
    assert len(candidates) == 2
    # 점수 높은 순 (Python+AWS 매칭 2개 > React 매칭 0개)
    assert candidates[0]["id"] == 1
    assert candidates[1]["id"] == 2
    assert all(c["fetched_at"] is not None for c in candidates)
