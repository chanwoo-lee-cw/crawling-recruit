from unittest.mock import patch, MagicMock
from services.naver.naver_client import NaverClient


MOCK_LIST_PAGE_1 = {
    "result": "Y",
    "list": [
        {
            "annoId": 30004786,
            "sysCompanyCdNm": "NAVER",
            "annoSubject": "[NAVER] 백엔드 개발자",
            "empTypeCdNm": "정규",
            "subJobCdNm": "Backend",
        }
    ],
    "totalSize": 1,
}

MOCK_DETAIL_HTML = "<html><body><div class='detail_wrap'><div class='detail_box'><h4 class='detail_title'>자격요건</h4><p class='detail_text'>Python 3년</p></div></div></body></html>"


def _mock_response(json_data=None, text_data=None, status=200):
    mock = MagicMock()
    mock.status_code = status
    if json_data is not None:
        mock.json.return_value = json_data
    if text_data is not None:
        mock.text = text_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_returns_list():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(json_data=MOCK_LIST_PAGE_1)
        client = NaverClient()
        jobs = client.fetch_jobs(limit_pages=1)
    assert len(jobs) == 1
    assert jobs[0]["annoId"] == 30004786
    assert jobs[0]["sysCompanyCdNm"] == "NAVER"


def test_fetch_jobs_stops_when_list_empty():
    empty_response = {"result": "Y", "list": [], "totalSize": 0}
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(json_data=empty_response)
        client = NaverClient()
        jobs = client.fetch_jobs()
    assert jobs == []
    assert mock_get.call_count == 1


def test_fetch_job_detail_returns_html():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_DETAIL_HTML, status=200)
        mock_get.return_value.raise_for_status = MagicMock()
        client = NaverClient()
        html = client.fetch_job_detail(30004786)
    assert html == MOCK_DETAIL_HTML


def test_fetch_job_detail_returns_none_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        client = NaverClient()
        html = client.fetch_job_detail(30004786)
    assert html is None
