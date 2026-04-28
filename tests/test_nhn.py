from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer

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


RAW_NHN_DETAIL = {
    "id": "4317632272881051418",
    "jobSeries": [
        {"id": "aaa", "name": "QA"},
        {"id": "aaa", "name": "QA"},  # 중복
        {"id": "bbb", "name": "Backend"},
    ],
    "jobPostingContentsItems": [
        {
            "title": "이런 분들을 찾고 있어요 (자격요건)",
            "contents": ["Python 3년 이상", "AWS 경험"],
        },
        {
            "title": "이런 분이면 더 좋아요 (우대사항)",
            "contents": ["FastAPI 경험자 우대"],
        },
        {
            "title": "주요업무",
            "contents": ["서비스 개발"],
        },
    ],
}


def test_parse_nhn_detail():
    parsed = NHNDetailSyncer._parse_nhn_detail(RAW_NHN_DETAIL)
    assert parsed["requirements"] == "Python 3년 이상\nAWS 경험"
    assert parsed["preferred_points"] == "FastAPI 경험자 우대"
    assert len(parsed["skill_tags"]) == 2
    tag_names = {t["text"] for t in parsed["skill_tags"]}
    assert "QA" in tag_names
    assert "Backend" in tag_names


def test_parse_nhn_detail_missing_sections():
    raw = {"id": "1", "jobSeries": [], "jobPostingContentsItems": []}
    parsed = NHNDetailSyncer._parse_nhn_detail(raw)
    assert parsed["requirements"] is None
    assert parsed["preferred_points"] is None
    assert parsed["skill_tags"] == []


def test_parse_nhn_applications_skips_incomplete():
    service = JobService(engine=MagicMock())
    result = service._parse_nhn_applications(RAW_NHN_APPS)
    assert len(result) == 1
    assert result[0]["job_platform_id"] == 3710991316958061032
    assert result[0]["platform_id"] == 4079920720933035925
    assert result[0]["status"] == "application-completed"
    assert result[0]["apply_time_str"] == "2026-04-20 12:18:00"
