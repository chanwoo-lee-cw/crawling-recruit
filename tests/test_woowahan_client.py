from unittest.mock import patch, MagicMock
from services.woowahan.woowahan_client import WoowahanClient

MOCK_LIST_PAGE_1 = {
    "code": "2000",
    "data": {
        "pageSize": 100,
        "pageNumber": 1,
        "totalPageNumber": 2,
        "totalSize": 18,
        "list": [
            {
                "recruitSeq": 24684,
                "recruitNumber": "R2604019",
                "recruitName": "Server(기술플랫폼개발)",
                "recruitOpenDate": "2026-04-20 17:30:00",
                "recruitEndDate": "9999-12-31 00:00:00",
                "employmentType": {"recruitItemGroupCode": "BA002", "recruitItemCode": "BA002001"},
                "careerType": {"recruitItemGroupCode": "BA003", "recruitItemCode": "BA003002"},
            }
        ],
    },
}
MOCK_LIST_PAGE_2 = {
    "code": "2000",
    "data": {
        "pageSize": 100, "pageNumber": 2, "totalPageNumber": 2, "totalSize": 18,
        "list": [
            {"recruitSeq": 24619, "recruitNumber": "R2411018", "recruitName": "WebFrontend", "recruitOpenDate": "2026-01-01 00:00:00", "recruitEndDate": "9999-12-31 00:00:00", "employmentType": {"recruitItemGroupCode": "BA002", "recruitItemCode": "BA002001"}, "careerType": {"recruitItemGroupCode": "BA003", "recruitItemCode": "BA003002"}},
        ],
    },
}
MOCK_DETAIL = {
    "code": "2000",
    "data": {"recruitSeq": 24619, "recruitNumber": "R2411018", "recruitName": "WebFrontend", "recruitContents": "<p>[지원자격] TypeScript 5년</p><p>[우대사항] React Native</p>"},
}


def _mock_response(json_data):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_paginates():
    with patch("httpx.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(MOCK_LIST_PAGE_1),
            _mock_response(MOCK_LIST_PAGE_2),
        ]
        jobs = WoowahanClient().fetch_jobs()
    assert len(jobs) == 2
    assert mock_get.call_count == 2


def test_fetch_job_detail():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(MOCK_DETAIL)
        detail = WoowahanClient().fetch_job_detail("R2411018")
    assert detail["recruitNumber"] == "R2411018"
    assert "recruitContents" in detail
