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
