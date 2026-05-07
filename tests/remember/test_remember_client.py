import pytest
from unittest.mock import AsyncMock, MagicMock, patch


SAMPLE_JOB = {
    "id": 308098,
    "title": "[ESTsecurity] 백엔드 개발",
    "qualifications": "Python 3년 이상",
    "preferred_qualifications": "FastAPI 경험자 우대",
    "organization": {"id": 21961, "name": "(주)이스트소프트", "company_id": 4494},
    "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
    "min_salary": None,
    "max_salary": None,
    "application": None,
}

SAMPLE_APPLICATION_JOB = {
    **SAMPLE_JOB,
    "id": 303872,
    "application": {
        "id": 3428290,
        "status": "applied",
        "applied_at": "2026-04-12T18:28:24.676+09:00",
    },
}


def _make_http_mock(status_code=200, json_data=None):
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_http.post.return_value = mock_resp
    mock_http.get.return_value = mock_resp
    return mock_http, mock_resp


async def test_fetch_jobs_success():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_AUTH_TOKEN": "test_token"}):
        mock_http, _ = _make_http_mock(200, {
            "data": [SAMPLE_JOB],
            "meta": {"total_pages": 1, "page": 1},
        })
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        jobs = await client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])

    assert len(jobs) == 1
    assert jobs[0]["id"] == 308098
    assert jobs[0]["qualifications"] == "Python 3년 이상"
    assert jobs[0]["organization"]["name"] == "(주)이스트소프트"


async def test_fetch_applications_success():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "test_cookie", "REMEMBER_AUTH_TOKEN": "test_token"}):
        mock_http, _ = _make_http_mock(200, {
            "data": [SAMPLE_APPLICATION_JOB],
            "meta": {"total_pages": 1, "page": 1},
        })
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        apps = await client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 303872
    assert apps[0]["application"]["id"] == 3428290
    assert apps[0]["application"]["status"] == "applied"


async def test_fetch_applications_raises_on_missing_cookie():
    with patch.dict("os.environ", {}, clear=True):
        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(ValueError, match="REMEMBER_COOKIE"):
            await client.fetch_applications()


async def test_fetch_applications_raises_on_expired_cookie():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "expired", "REMEMBER_AUTH_TOKEN": "tok"}):
        mock_http, _ = _make_http_mock(401)
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(PermissionError, match="만료"):
            await client.fetch_applications()


async def test_fetch_jobs_http_error():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_AUTH_TOKEN": "test_token"}):
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_http.post.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(Exception, match="500"):
            await client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])
