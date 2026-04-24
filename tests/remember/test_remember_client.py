import pytest
from unittest.mock import patch, MagicMock


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


def test_fetch_jobs_success():
    with patch("services.remember.remember_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [SAMPLE_JOB],
            "meta": {"total_pages": 1, "page": 1},
        }
        mock_httpx.post.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        jobs = client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])

    assert len(jobs) == 1
    assert jobs[0]["id"] == 308098
    assert jobs[0]["qualifications"] == "Python 3년 이상"
    assert jobs[0]["organization"]["name"] == "(주)이스트소프트"


def test_fetch_applications_success():
    with patch("services.remember.remember_client.httpx") as mock_httpx, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "test_cookie"}):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [SAMPLE_APPLICATION_JOB],
            "meta": {"total_pages": 1, "page": 1},
        }
        mock_httpx.get.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        apps = client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 303872
    assert apps[0]["application"]["id"] == 3428290
    assert apps[0]["application"]["status"] == "applied"


def test_fetch_applications_raises_on_missing_cookie():
    with patch.dict("os.environ", {}, clear=True):
        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(ValueError, match="REMEMBER_COOKIE"):
            client.fetch_applications()


def test_fetch_applications_raises_on_expired_cookie():
    with patch("services.remember.remember_client.httpx") as mock_httpx, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "expired"}):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_httpx.get.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(PermissionError, match="만료"):
            client.fetch_applications()


def test_fetch_jobs_http_error():
    with patch("services.remember.remember_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_httpx.post.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(Exception, match="500"):
            client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])
