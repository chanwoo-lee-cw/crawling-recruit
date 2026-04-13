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
    mock_conn.execute.return_value.rowcount = 1

    service = JobService(engine=mock_engine)
    result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_conn.execute.called
    assert "동기화 완료:" in result
    assert "신규" in result
    assert "변경" in result
    assert "유지" in result


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
