from unittest.mock import MagicMock, patch


def test_kt_client_fetch_jobs():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "isSuccess": True,
        "data": [
            {
                "recruitNoticeSn": 251744,
                "recruitNoticeName": "[kt] 백엔드 개발자 채용",
                "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
                "recruitClassName": "경력",
                "receiveStartDatetime": "2026-04-23 10:00:00",
                "company": "KT",
                "title": "백엔드 개발자",
            }
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("services.kt.kt_client.httpx.get", return_value=mock_resp):
        from services.kt.kt_client import KTClient
        jobs = KTClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["recruitNoticeSn"] == 251744


def test_parse_kt_job():
    from services.jobs.job_service import JobService
    raw = {
        "recruitNoticeSn": 251744,
        "recruitNoticeName": "[kt] 백엔드 개발자 채용",
        "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
        "recruitClassName": "경력",
        "receiveStartDatetime": "2026-04-23 10:00:00",
        "company": "KT",
        "title": "백엔드 개발자",
    }
    result = JobService.__new__(JobService)._parse_kt_job(raw)
    assert result["source"] == "kt"
    assert result["platform_id"] == 107620
    assert result["title"] == "백엔드 개발자"
    assert result["company_name"] == "KT"


def test_build_job_url_kt():
    from services.jobs.job_service import build_job_url
    url = build_job_url("kt", 107620)
    assert "kt.recruiter.co.kr" in url
    assert "107620" in url


SAMPLE_KT_CONTENTS = """
<div>
  <p><span>kt</span><span> STUDIO</span></p>
  <p>●담당업무</p>
  <p>-서버 개발 및 운영</p>
  <p>●필수요건</p>
  <p>-<span>Java</span>, <span>Spring</span> 개발 경력 3년 이상</p>
  <p>-RDBMS 활용 경험</p>
  <p>●우대사항</p>
  <p>-Kubernetes 운영 경험</p>
  <p>●보고 체계 및 협업 부서</p>
  <p>-주요 보고 대상: 팀장</p>
</div>
"""


def test_kt_client_requests_contents_when_asked():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("services.kt.kt_client.httpx.get", return_value=mock_resp) as mock_get:
        from services.kt.kt_client import KTClient
        KTClient().fetch_jobs(include_contents=True)
    assert mock_get.call_args.kwargs["params"]["isContainsContents"] == 1


def test_kt_client_omits_contents_by_default():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status = MagicMock()
    with patch("services.kt.kt_client.httpx.get", return_value=mock_resp) as mock_get:
        from services.kt.kt_client import KTClient
        KTClient().fetch_jobs()
    assert mock_get.call_args.kwargs["params"]["isContainsContents"] == 0


def test_extract_kt_platform_id_prefers_notice_url():
    from services.kt.kt_constants import extract_kt_platform_id
    raw = {"recruitNoticeSn": 251744, "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620"}
    assert extract_kt_platform_id(raw) == 107620


def test_extract_kt_platform_id_falls_back_to_sn():
    from services.kt.kt_constants import extract_kt_platform_id
    assert extract_kt_platform_id({"recruitNoticeSn": 251744}) == 251744


def test_kt_detail_syncer_parses_sections():
    from services.kt.kt_detail_syncer import KTDetailSyncer
    parsed = KTDetailSyncer._parse_contents_html(SAMPLE_KT_CONTENTS)
    assert "Java, Spring 개발 경력 3년 이상" in parsed["requirements"]
    assert "RDBMS 활용 경험" in parsed["requirements"]
    assert "Kubernetes 운영 경험" in parsed["preferred_points"]
    assert "주요 보고 대상" not in (parsed["preferred_points"] or "")


def test_kt_detail_syncer_returns_message_when_no_targets():
    import asyncio
    from services.kt.kt_detail_syncer import KTDetailSyncer
    service = MagicMock()
    service.get_jobs_without_details.return_value = []
    assert asyncio.run(KTDetailSyncer(service).sync()) == "처리할 공고가 없습니다."


def test_kt_detail_syncer_matches_contents_by_platform_id():
    """KT는 리스트 API 한 번으로 본문까지 받으므로 공고별 재요청이 없다."""
    import asyncio
    from services.kt.kt_detail_syncer import KTDetailSyncer
    service = MagicMock()
    service.get_jobs_without_details.return_value = [(7, 107620)]
    service.upsert_job_details.return_value = "완료: 1개 처리"
    with patch("services.kt.kt_detail_syncer.KTClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = [{
            "recruitNoticeSn": 251744,
            "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
            "contents": SAMPLE_KT_CONTENTS,
        }]
        result = asyncio.run(KTDetailSyncer(service).sync())
        MockClient.return_value.fetch_jobs.assert_called_once_with(include_contents=True)
    details = service.upsert_job_details.call_args[0][0]
    assert len(details) == 1 and details[0].job_id == 7
    assert "Java, Spring" in details[0].requirements
    assert result == "완료: 1개 처리"


def test_kt_detail_syncer_skips_jobs_without_contents():
    import asyncio
    from services.kt.kt_detail_syncer import KTDetailSyncer
    service = MagicMock()
    service.get_jobs_without_details.return_value = [(7, 107620)]
    with patch("services.kt.kt_detail_syncer.KTClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = [{
            "recruitNoticeUrl": "https://kt.recruiter.co.kr/career/jobs/107620",
            "contents": "",
        }]
        result = asyncio.run(KTDetailSyncer(service).sync())
    assert result == "상세 정보를 가져온 공고가 없습니다."
    assert not service.upsert_job_details.called


def test_kt_detail_syncer_handles_check_marker_headings():
    """KT 공고마다 섹션 마커가 다르다 (●, ✓, ■ 등)."""
    from services.kt.kt_detail_syncer import KTDetailSyncer
    html = """
    <div>
      <p>✓ 담당 업무</p>
      <p>서버 개발</p>
      <p>✓ 자격 요건</p>
      <p>Java 개발 경력 3년 이상</p>
      <p>✓ 우대 사항</p>
      <p>Kafka 경험</p>
    </div>
    """
    parsed = KTDetailSyncer._parse_contents_html(html)
    assert parsed["requirements"] == "Java 개발 경력 3년 이상"
    assert parsed["preferred_points"] == "Kafka 경험"


def test_kt_detail_syncer_returns_none_for_image_only_posting():
    """본문이 이미지뿐인 공고는 뽑을 텍스트가 없다."""
    from services.kt.kt_detail_syncer import KTDetailSyncer
    parsed = KTDetailSyncer._parse_contents_html('<div><img src="x.png"></div>')
    assert parsed["requirements"] is None
    assert parsed["preferred_points"] is None
