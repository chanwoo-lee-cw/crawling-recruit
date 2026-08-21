from unittest.mock import MagicMock, patch


def test_cj_client_fetch_jobs_returns_list():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "ds_newRecruitList": [
            {"zz_jo_num": "J20260319037841", "zz_title": "Backend Dev", "compnm": "CJ ENM",
             "location_cd_nm": "서울", "tot_cnt": 1}
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("services.cj.cj_client.httpx.post", return_value=mock_response):
        from services.cj.cj_client import CJClient
        jobs = CJClient().fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["zz_jo_num"] == "J20260319037841"


def test_parse_cj_job():
    from services.jobs.job_service import JobService
    raw = {
        "zz_jo_num": "J20260319037841",
        "zz_title": "Backend Dev",
        "compnm": "CJ ENM",
        "location_cd_nm": "서울",
        "tot_cnt": 1,
    }
    result = JobService.__new__(JobService)._parse_cj_job(raw)
    assert result["source"] == "cj"
    assert result["platform_id"] == 20260319037841
    assert result["title"] == "Backend Dev"
    assert result["company_name"] == "CJ ENM"
    assert result["location"] == "서울"


def test_cj_syncer_calls_upsert():
    with patch("services.cj.cj_syncer.CJClient") as MockClient, \
         patch("services.cj.cj_syncer.BaseSyncer.__init__", return_value=None):
        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = [{"zz_jo_num": "J123", "zz_title": "Dev"}]
        MockClient.return_value = mock_client

        from services.cj.cj_syncer import CJSyncer
        import asyncio
        syncer = CJSyncer.__new__(CJSyncer)
        syncer.service = MagicMock()
        syncer.service.upsert_jobs.return_value = "동기화 완료: 신규 1개"
        result = asyncio.run(syncer.sync())

    assert "동기화" in result
    syncer.service.upsert_jobs.assert_called_once()


def test_cj_detail_syncer_returns_message_when_fetch_fails():
    import asyncio
    from services.cj.cj_detail_syncer import CJDetailSyncer
    syncer = CJDetailSyncer.__new__(CJDetailSyncer)
    syncer.service = MagicMock()
    syncer.service.get_jobs_without_details.return_value = [(11, 20260319037841)]
    with patch("services.cj.cj_detail_syncer.CJClient") as MockClient:
        MockClient.return_value.fetch_job_detail.return_value = None
        result = asyncio.run(syncer.sync())
    assert result == "상세 정보를 가져온 공고가 없습니다."


def test_build_job_url_cj():
    from services.jobs.job_service import build_job_url
    url = build_job_url("cj", 20260319037841)
    assert "J20260319037841" in url
    assert "recruit.cj.net" in url


SAMPLE_CJ_DETAIL_HTML = """
<div class="detail">
  <div class="tit">[TES물류기술연구소] 로봇 S/W Engineer 경력사원 모집</div>
  <ul>
    <li><h3>직무소개</h3>[부서소개]
      Robotics팀은 물류 자동화를 개발합니다.</li>
    <li><h3>지원자격</h3>- 석사 이상
      - Java, Spring 개발 경력 3년 이상</li>
    <li><h3>우대사항</h3>- Kubernetes 운영 경험
      - 커뮤니케이션 역량</li>
    <li><h3>기타 안내사항</h3>[전형절차] 서류전형 - 면접</li>
  </ul>
</div>
"""


def test_cj_client_builds_best_detail_url():
    mock_resp = MagicMock(status_code=200, text="<html></html>")
    mock_resp.raise_for_status = MagicMock()
    with patch("services.cj.cj_client.httpx.get", return_value=mock_resp) as mock_get:
        from services.cj.cj_client import CJClient
        CJClient().fetch_job_detail(20260813039265)
    url = mock_get.call_args[0][0]
    assert "bestDetail.fo" in url
    assert "zz_jo_num=J20260813039265" in url


def test_cj_client_fetch_job_detail_returns_none_on_error():
    with patch("services.cj.cj_client.httpx.get", side_effect=Exception("boom")):
        from services.cj.cj_client import CJClient
        assert CJClient().fetch_job_detail(1) is None


def test_cj_detail_syncer_parses_sections():
    from services.cj.cj_detail_syncer import CJDetailSyncer
    parsed = CJDetailSyncer._parse_detail_html(SAMPLE_CJ_DETAIL_HTML)
    assert "Java, Spring 개발 경력 3년 이상" in parsed["requirements"]
    assert "Kubernetes 운영 경험" in parsed["preferred_points"]
    assert "전형절차" not in (parsed["requirements"] or "")
    assert "전형절차" not in (parsed["preferred_points"] or "")


def test_cj_detail_syncer_includes_job_intro_in_requirements():
    """직무소개는 기술 스택 단서를 담고 있어 requirements에 함께 넣는다."""
    from services.cj.cj_detail_syncer import CJDetailSyncer
    parsed = CJDetailSyncer._parse_detail_html(SAMPLE_CJ_DETAIL_HTML)
    assert "물류 자동화" in parsed["requirements"]


def test_cj_detail_syncer_returns_message_when_no_targets():
    import asyncio
    from services.cj.cj_detail_syncer import CJDetailSyncer
    service = MagicMock()
    service.get_jobs_without_details.return_value = []
    result = asyncio.run(CJDetailSyncer(service).sync())
    assert result == "처리할 공고가 없습니다."


def test_cj_detail_syncer_upserts_fetched_details():
    import asyncio
    from services.cj.cj_detail_syncer import CJDetailSyncer
    service = MagicMock()
    service.get_jobs_without_details.return_value = [(11, 20260813039265)]
    service.upsert_job_details.return_value = "완료: 1개 처리"
    with patch("services.cj.cj_detail_syncer.CJClient") as MockClient, \
         patch("services.cj.cj_detail_syncer.time.sleep"):
        MockClient.return_value.fetch_job_detail.return_value = SAMPLE_CJ_DETAIL_HTML
        result = asyncio.run(CJDetailSyncer(service).sync())
    details = service.upsert_job_details.call_args[0][0]
    assert len(details) == 1
    assert details[0].job_id == 11
    assert "Java, Spring" in details[0].requirements
    assert result == "완료: 1개 처리"


def test_cj_detail_syncer_does_not_fragment_inline_spans():
    """인라인 span으로 쪼개진 문장이 '영상 / · / 이미지'처럼 조각나면 안 된다."""
    from services.cj.cj_detail_syncer import CJDetailSyncer
    html = """
    <div class="detail"><ul>
      <li><h3>지원자격</h3>
        <p><span>영상</span>·<span>이미지</span> 처리 경험 <span>3</span>년 이상</p>
        <p>Java, Spring 경험</p>
      </li>
    </ul></div>
    """
    parsed = CJDetailSyncer._parse_detail_html(html)
    assert "영상·이미지 처리 경험 3년 이상" in parsed["requirements"]
    assert "Java, Spring 경험" in parsed["requirements"]
