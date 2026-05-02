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
