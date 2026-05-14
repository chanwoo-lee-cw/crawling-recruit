from unittest.mock import MagicMock, patch

SAMPLE_DETAIL_HTML = """
<div class="detail-content-item">
  <h3 class="detail-content-title">이런 분과 함께 하고 싶습니다.</h3>
  <div class="item-column">
    <strong class="item-label">지원자격</strong>
    <div class="item-field">
      <ul class="asset-list">
        <li>DevOps 경력 5년 이상</li>
        <li>Kubernetes 운영 경험</li>
      </ul>
    </div>
  </div>
</div>
<div class="detail-content-item">
  <h3 class="detail-content-title">이런 경험이 있다면 더 환영합니다.</h3>
  <div class="item-column">
    <ul class="asset-list">
      <li>Karpenter 경험</li>
      <li>ArgoCD 경험</li>
    </ul>
  </div>
</div>
"""


def test_sk_client_fetch_jobs():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "list": [
            {"jobNoticeNo": 4559, "noticeID": "R260107", "title": "DevOps Engineer",
             "corpName": "티맵모빌리티", "workingType": "정규", "workingArea": "서울"}
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("services.sk.sk_client.httpx.post", return_value=mock_resp):
        from services.sk.sk_client import SKClient
        jobs = SKClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["noticeID"] == "R260107"


def test_parse_sk_job():
    from services.jobs.job_service import JobService
    raw = {"jobNoticeNo": 4559, "noticeID": "R260107", "title": "DevOps Engineer",
           "corpName": "티맵모빌리티", "workingType": "정규", "workingArea": "서울"}
    result = JobService.__new__(JobService)._parse_sk_job(raw)
    assert result["source"] == "sk"
    assert result["platform_id"] == 260107
    assert result["title"] == "DevOps Engineer"
    assert result["company_name"] == "티맵모빌리티"
    assert result["employment_type"] == "regular"
    assert result["location"] == "서울"


def test_sk_detail_syncer_parse_html():
    from services.sk.sk_detail_syncer import SKDetailSyncer
    parsed = SKDetailSyncer._parse_detail_html(SAMPLE_DETAIL_HTML)
    assert "DevOps 경력 5년 이상" in parsed["requirements"]
    assert "Kubernetes 운영 경험" in parsed["requirements"]
    assert "Karpenter 경험" in parsed["preferred_points"]
    assert "ArgoCD 경험" in parsed["preferred_points"]


def test_build_job_url_sk():
    from services.jobs.job_service import build_job_url
    url = build_job_url("sk", 260107)
    assert "skcareers.com" in url
    assert "R260107" in url
