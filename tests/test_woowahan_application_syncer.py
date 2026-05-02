from unittest.mock import MagicMock
from services.jobs.job_service import JobService

RAW_WOOWAHAN_APPS = [
    {
        "applicationSeq": 100251475,
        "applicationDate": "2025-08-12 04:05:16",
        "applicationFinalYn": True,
        "applicationJudgmentStatesCode": {"code": "PASS", "text": "서류합격"},
        "recruitSeq": 22451,
        "recruitNumber": "R2409006",
        "recruitName": "백엔드 개발",
        "isEndedRecruit": False,
    },
    {
        "applicationSeq": 100262742,
        "applicationDate": "2026-01-06 21:03:53",
        "applicationFinalYn": False,
        "applicationJudgmentStatesCode": {"code": "TEMPORARY", "text": "임시저장"},
        "recruitSeq": 23189,
        "recruitNumber": "R2509015",
        "recruitName": "서버 개발",
        "isEndedRecruit": False,
    },
]


def test_parse_woowahan_applications_skips_temporary():
    service = JobService(engine=MagicMock())
    result = service._parse_woowahan_applications(RAW_WOOWAHAN_APPS)
    assert len(result) == 1
    assert result[0]["platform_id"] == 100251475
    assert result[0]["job_platform_id"] == 2409006   # int("R2409006"[1:])
    assert result[0]["status"] == "PASS"
    assert result[0]["apply_time_str"] == "2025-08-12 04:05:16"
