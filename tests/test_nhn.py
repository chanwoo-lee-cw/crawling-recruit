from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN

RAW_NHN_JOB = {
    "id": "4317632272881051418",
    "corporation": {
        "id": "3673339512358903254",
        "name": "NHN COMMERCE",
    },
    "name": "커머스 솔루션 QA 담당자",
    "finishYn": "N",
    "employeeType": {"name": "정규"},
    "jobSeries": [
        {"id": "aaa", "name": "QA"},
        {"id": "aaa", "name": "QA"},  # 중복
        {"id": "bbb", "name": "Backend"},
    ],
}

RAW_NHN_APPS = [
    {
        "jobPostingName": "백엔드 개발",
        "jobPostingId": "3710991316958061032",
        "applicationId": "4079920720933035925",
        "displayStepButtonCd": "application-completed",
        "finalSubmitYn": "Y",
        "finalSubmitDatetime": "2026-04-20 12:18",
    },
    {
        "jobPostingName": "미완료 지원",
        "jobPostingId": "1111111111111111111",
        "applicationId": "2222222222222222222",
        "displayStepButtonCd": "write",
        "finalSubmitYn": "N",
        "finalSubmitDatetime": None,
    },
]


def test_parse_nhn_job():
    service = JobService(engine=MagicMock())
    row = service._parse_nhn_job(RAW_NHN_JOB)
    assert row["source"] == NHN
    assert row["platform_id"] == 4317632272881051418
    assert row["company_id"] is None
    assert row["company_name"] == "NHN COMMERCE"
    assert row["title"] == "커머스 솔루션 QA 담당자"
    assert row["employment_type"] == "regular"
    assert row["location"] is None
    assert row["job_group_id"] is None
    assert row["category_tag_id"] is None
    assert row["is_active"] is True


def test_parse_nhn_applications_skips_incomplete():
    service = JobService(engine=MagicMock())
    result = service._parse_nhn_applications(RAW_NHN_APPS)
    assert len(result) == 1
    assert result[0]["job_platform_id"] == 3710991316958061032
    assert result[0]["platform_id"] == 4079920720933035925
    assert result[0]["status"] == "application-completed"
    assert result[0]["apply_time_str"] == "2026-04-20 12:18:00"
