from unittest.mock import patch, MagicMock
from services.kakaobank.kakaobank_client import KakaoBankClient

MOCK_LIST_PAGE_1 = {
    "paging": {"pageNumber": 0, "pageSize": 20, "totalPages": 2, "totalElements": 25},
    "list": [
        {
            "recruitNoticeSn": 251760,
            "recruitNoticeName": "iOS 앱 개발자",
            "recruitNoticeUrl": "kakaobank.recruiter.co.kr/...",
            "recruitTypeName": "일반채용",
            "recruitClassName": "Mobile",
            "receiveStartDatetime": "2026-04-27 00:00:00",
            "receiveEndDatetime": "2026-05-14 23:59:59",
        }
    ],
}
MOCK_LIST_PAGE_2 = {
    "paging": {"pageNumber": 1, "pageSize": 20, "totalPages": 2, "totalElements": 25},
    "list": [{"recruitNoticeSn": 247114, "recruitNoticeName": "서비스 기획자", "recruitTypeName": "일반채용", "recruitClassName": "Service & Biz", "receiveStartDatetime": "2026-03-09 00:00:00", "receiveEndDatetime": "2026-04-30 23:59:59", "recruitNoticeUrl": ""}],
}
MOCK_DETAIL = {
    "recruitNoticeSn": 251760,
    "recruitNoticeName": "iOS 앱 개발자",
    "recruitTypeName": "일반채용",
    "recruitClassName": "Mobile",
    "receiveStartDatetime": "2026-04-27 00:00:00",
    "receiveEndDatetime": "2026-05-14 23:59:59",
    "contents": "<div class='desc_cont'><div class='tit'>필수 경험과 역량</div><div class='cont'><p>Swift 개발 4년</p></div></div>",
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
        jobs = KakaoBankClient().fetch_jobs()
    assert len(jobs) == 2
    assert mock_get.call_count == 2


def test_fetch_jobs_stops_when_no_more_pages():
    single_page = {
        "paging": {"pageNumber": 0, "pageSize": 20, "totalPages": 1, "totalElements": 1},
        "list": [MOCK_LIST_PAGE_1["list"][0]],
    }
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(single_page)
        jobs = KakaoBankClient().fetch_jobs()
    assert len(jobs) == 1
    assert mock_get.call_count == 1


def test_fetch_job_detail():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(MOCK_DETAIL)
        detail = KakaoBankClient().fetch_job_detail(251760)
    assert detail["recruitNoticeSn"] == 251760
    assert "contents" in detail
