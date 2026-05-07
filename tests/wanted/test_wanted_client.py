import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.wanted.wanted_client import WantedClient
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


def _make_http_mock(status_code=200, json_data=None):
    """httpx.AsyncClient 인스턴스 mock을 반환한다."""
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_http.get.return_value = mock_resp
    mock_http.post.return_value = mock_resp
    return mock_http, mock_resp


async def test_fetch_jobs_single_page():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_JOBS_PAGE_1)
        mock_cls.return_value = mock_http

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518)

    assert len(jobs) == 1
    assert jobs[0]["id"] == 1001


async def test_fetch_jobs_respects_limit_pages():
    page_with_next = {
        "data": [{"id": i, "company": {"id": 1, "name": "A"}, "position": "Dev",
                  "address": {"location": "서울"}, "employment_type": "regular",
                  "annual_from": 0, "annual_to": 0, "job_group_id": 518,
                  "category_tag": {"parent_id": 518, "id": 872},
                  "create_time": "2026-01-01T00:00:00"}
                 for i in range(20)],
        "links": {"next": "/api/next?offset=20"}
    }
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_with_next
        mock_http.get.return_value = mock_resp

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518, limit_pages=2)

    assert mock_http.get.call_count == 2
    assert len(jobs) == 40


async def test_fetch_applications_requires_cookie():
    client = WantedClient(cookie=None, user_id="123")
    with pytest.raises(ValueError, match="WANTED_COOKIE"):
        await client.fetch_applications()


async def test_fetch_applications_raises_on_401():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(status_code=401)
        mock_cls.return_value = mock_http

        client = WantedClient(cookie="test-cookie", user_id="123")
        with pytest.raises(PermissionError, match="쿠키"):
            await client.fetch_applications()


async def test_fetch_applications_single_page():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_APPS_PAGE_1)
        mock_cls.return_value = mock_http

        client = WantedClient(cookie="test-cookie", user_id="123")
        apps = await client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 9001


async def test_retry_on_429():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls, \
         patch("services.wanted.wanted_client.asyncio.sleep") as mock_sleep:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = MOCK_JOBS_PAGE_1

        mock_http.get.side_effect = [rate_limit_resp, rate_limit_resp, ok_resp]

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518)

    assert mock_http.get.call_count == 3
    assert mock_sleep.call_count == 2
    assert len(jobs) == 1


async def test_retry_exhausted_raises():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls, \
         patch("services.wanted.wanted_client.asyncio.sleep"):
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}
        mock_http.get.return_value = rate_limit_resp

        client = WantedClient()
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            await client.fetch_jobs(job_group_id=518)


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


async def test_fetch_job_detail_success():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_DETAIL_RESPONSE)
        mock_cls.return_value = mock_http

        client = WantedClient()
        result = await client.fetch_job_detail(210918)

    assert result is not None
    assert isinstance(result, JobDetail)
    assert result.job_id == 210918
    assert result.requirements == "Python 3년 이상"
    assert result.preferred_points == "FastAPI 경험자 우대"
    assert result.skill_tags == [
        {"tag_type_id": 1554, "text": "Python"},
        {"tag_type_id": 1562, "text": "SQL"},
    ]


async def test_fetch_job_detail_returns_none_on_error():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(404)
        mock_cls.return_value = mock_http

        client = WantedClient()
        result = await client.fetch_job_detail(99999)

    assert result is None
