from unittest.mock import MagicMock, patch


def test_kt_client_fetch_jobs():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "isSuccess": True,
        "data": [
            {
                "recruitNoticeSn": 251744,
                "recruitNoticeName": "[kt] 백엔드 개발자 채용",
                "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
                "recruitClassName": "경력",
                "receiveStartDatetime": "2026-04-23 10:00:00",
                "company": "KT",
                "title": "백엔드 개발자",
            }
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("services.kt.kt_client.httpx.get", return_value=mock_resp):
        from services.kt.kt_client import KTClient
        jobs = KTClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["recruitNoticeSn"] == 251744


def test_parse_kt_job():
    from services.jobs.job_service import JobService
    raw = {
        "recruitNoticeSn": 251744,
        "recruitNoticeName": "[kt] 백엔드 개발자 채용",
        "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
        "recruitClassName": "경력",
        "receiveStartDatetime": "2026-04-23 10:00:00",
        "company": "KT",
        "title": "백엔드 개발자",
    }
    result = JobService.__new__(JobService)._parse_kt_job(raw)
    assert result["source"] == "kt"
    assert result["platform_id"] == 107620
    assert result["title"] == "백엔드 개발자"
    assert result["company_name"] == "KT"


def test_build_job_url_kt():
    from services.jobs.job_service import build_job_url
    url = build_job_url("kt", 107620)
    assert "kt.recruiter.co.kr" in url
    assert "107620" in url
