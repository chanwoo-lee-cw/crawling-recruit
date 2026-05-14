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


def test_cj_detail_syncer_returns_message():
    import asyncio
    from services.cj.cj_detail_syncer import CJDetailSyncer
    syncer = CJDetailSyncer.__new__(CJDetailSyncer)
    syncer.service = MagicMock()
    result = asyncio.run(syncer.sync())
    assert "지원하지 않습니다" in result


def test_build_job_url_cj():
    from services.jobs.job_service import build_job_url
    url = build_job_url("cj", 20260319037841)
    assert "J20260319037841" in url
    assert "recruit.cj.net" in url
