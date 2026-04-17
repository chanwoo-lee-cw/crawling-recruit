import pytest
from unittest.mock import patch, MagicMock
from services.wanted_client import WantedClient
from domain import JobDetail


MOCK_JOBS_PAGE_1 = {
    "data": [
        {
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
    ],
    "links": {"next": None}
}

MOCK_APPS_PAGE_1 = {
    "applications": [
        {
            "id": 9001,
            "job_id": 2001,
            "status": "complete",
            "apply_time": "2026-01-01T00:00:00",
        }
    ],
    "total": 1,
    "links": {"next": None}
}


def test_fetch_jobs_single_page():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_JOBS_PAGE_1
        mock_get.return_value = mock_resp

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518)

    assert len(jobs) == 1
    assert jobs[0]["id"] == 1001


def test_fetch_jobs_respects_limit_pages():
    page_with_next = {
        "data": [{"id": i, "company": {"id": 1, "name": "A"}, "position": "Dev",
                  "address": {"location": "서울"}, "employment_type": "regular",
                  "annual_from": 0, "annual_to": 0, "job_group_id": 518,
                  "category_tag": {"parent_id": 518, "id": 872},
                  "create_time": "2026-01-01T00:00:00"}
                 for i in range(20)],
        "links": {"next": "/api/next?offset=20"}
    }
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_with_next
        mock_get.return_value = mock_resp

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518, limit_pages=2)

    assert mock_get.call_count == 2
    assert len(jobs) == 40


def test_fetch_applications_requires_cookie():
    client = WantedClient(cookie=None, user_id="123")
    with pytest.raises(ValueError, match="WANTED_COOKIE"):
        client.fetch_applications()


def test_fetch_applications_raises_on_401():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        client = WantedClient(cookie="test-cookie", user_id="123")
        with pytest.raises(PermissionError, match="쿠키"):
            client.fetch_applications()


def test_fetch_applications_single_page():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_APPS_PAGE_1
        mock_get.return_value = mock_resp

        client = WantedClient(cookie="test-cookie", user_id="123")
        apps = client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 9001


def test_retry_on_429():
    with patch("services.wanted_client.httpx.get") as mock_get, \
         patch("services.wanted_client.time.sleep") as mock_sleep:
        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = MOCK_JOBS_PAGE_1

        mock_get.side_effect = [rate_limit_resp, rate_limit_resp, ok_resp]

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518)

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    assert len(jobs) == 1


def test_retry_exhausted_raises():
    with patch("services.wanted_client.httpx.get") as mock_get, \
         patch("services.wanted_client.time.sleep"):
        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}
        mock_get.return_value = rate_limit_resp

        client = WantedClient()
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            client.fetch_jobs(job_group_id=518)


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
    assert isinstance(result, JobDetail)
    assert result.job_id == 210918
    assert result.requirements == "Python 3년 이상"
    assert result.preferred_points == "FastAPI 경험자 우대"
    assert result.skill_tags == [
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
