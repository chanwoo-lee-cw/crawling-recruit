from unittest.mock import patch, MagicMock
from services.coupang.coupang_client import CoupangClient

MOCK_LIST_HTML = """
<html><body>
<div class="grid job-listing" id="js-job-search-results">
  <div class="card card-job">
    <div class="card-body">
      <h2 class="card-title">
        <a class="stretched-link js-view-job" href="/kr/jobs/7230716/staff-back-end-engineer/">
          Staff Back-end Engineer
        </a>
      </h2>
      <div class="card-job-actions js-job" data-id="7230716" data-jobtitle="Staff Back-end Engineer"></div>
      <ul class="list-inline job-meta">
        <li class="list-inline-item">대한민국</li>
      </ul>
    </div>
  </div>
</div>
</body></html>
"""

MOCK_DETAIL_HTML = """
<html><body>
<div class="main-col">
  <article class="cms-content">
    <div><strong>자격 요건</strong></div>
    <ul><li>Python 3년 이상</li><li>AWS 경험</li></ul>
    <div><strong>우대 사항</strong></div>
    <ul><li>FastAPI 경험 우대</li></ul>
  </article>
</div>
</body></html>
"""


def _mock_response(text_data="", status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = text_data
    mock.raise_for_status = MagicMock()
    return mock


def test_fetch_jobs_parses_cards():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_LIST_HTML)
        jobs = CoupangClient().fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == 7230716
    assert jobs[0]["title"] == "Staff Back-end Engineer"
    assert jobs[0]["location"] == "대한민국"


def test_fetch_jobs_empty_page():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data="<html><body></body></html>")
        jobs = CoupangClient().fetch_jobs()
    assert jobs == []


def test_fetch_job_detail_returns_html():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = _mock_response(text_data=MOCK_DETAIL_HTML)
        html = CoupangClient().fetch_job_detail(7230716)
    assert html == MOCK_DETAIL_HTML


def test_fetch_job_detail_returns_none_on_error():
    with patch("httpx.get", side_effect=Exception("network error")):
        html = CoupangClient().fetch_job_detail(7230716)
    assert html is None
