from unittest.mock import MagicMock, patch

SAMPLE_LIST_HTML = """
<ul>
  <li>
    <div>
      <a href="/#none" data-value="22,248">
        <p class="company">삼성SDI</p>
        <h3 class="title">경력사원 채용</h3>
        <p class="info">
          <span>경력</span>
          <span class="period">2026.05.04 ~ 2026.05.18</span>
        </p>
      </a>
    </div>
  </li>
</ul>
"""

SAMPLE_DETAIL_JSON = {
    "result": {"seq": 22248, "qlfctKr": "공통 자격요건"},
    "items": [
        {"titleKr": "포지션A", "qlfctKr": "Python 3년", "favorKr": "ML 경험"},
        {"titleKr": "포지션B", "qlfctKr": "Java 5년", "favorKr": "MSA 경험"},
    ],
}


def test_samsung_client_parse_list_html():
    from services.samsung.samsung_client import SamsungClient
    jobs = SamsungClient._parse_list_html(SAMPLE_LIST_HTML)
    assert len(jobs) == 1
    assert jobs[0]["id"] == 22248
    assert jobs[0]["company"] == "삼성SDI"
    assert jobs[0]["title"] == "경력사원 채용"
    assert jobs[0]["employment_type"] == "경력"


def test_parse_samsung_job():
    from services.jobs.job_service import JobService
    raw = {"id": 22248, "company": "삼성SDI", "title": "경력사원 채용", "employment_type": "경력"}
    result = JobService.__new__(JobService)._parse_samsung_job(raw)
    assert result["source"] == "samsung"
    assert result["platform_id"] == 22248
    assert result["title"] == "경력사원 채용"
    assert result["employment_type"] is None  # "경력" not in EMPLOYMENT_TYPE_MAP


def test_samsung_detail_syncer_parse_detail():
    from services.samsung.samsung_detail_syncer import SamsungDetailSyncer
    parsed = SamsungDetailSyncer._parse_detail(SAMPLE_DETAIL_JSON)
    assert "공통 자격요건" in parsed["requirements"]
    assert "Python 3년" in parsed["requirements"]
    assert "Java 5년" in parsed["requirements"]
    assert "ML 경험" in parsed["preferred_points"]
    assert "MSA 경험" in parsed["preferred_points"]


def test_build_job_url_samsung():
    from services.jobs.job_service import build_job_url
    url = build_job_url("samsung", 22248)
    assert "samsungcareers.com" in url
    assert "22248" in url
    assert "seqno=" in url
