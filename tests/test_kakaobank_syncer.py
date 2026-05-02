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
