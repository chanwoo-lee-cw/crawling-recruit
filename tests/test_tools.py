from unittest.mock import patch, MagicMock
from domain import JobDetail
from constants.constants import CRAWL_DELAY_SECONDS, DEFAULT_LIMIT_PAGES
from constants.wanted_constants import WANTED


def test_sync_jobs_uses_preset_when_given():
    with patch("tools.sync_jobs.get_engine") as mock_engine, \
         patch("services.syncer.WantedClient") as mock_client_cls, \
         patch("tools.sync_jobs.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.get_preset_params.return_value = {"job_group_id": 519}
        mock_service.upsert_jobs.return_value = "동기화 완료: 신규/변경 5개, 총 5개 처리"
        mock_service_cls.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = []
        mock_client_cls.return_value = mock_client

        from tools.sync_jobs import sync_jobs
        result = sync_jobs(preset_name="백엔드 신입")

    mock_service.get_preset_params.assert_called_once_with("백엔드 신입")
    mock_service.upsert_jobs.assert_called_once()
    call_kwargs = mock_client.fetch_jobs.call_args.kwargs
    assert call_kwargs.get("job_group_id") == 519


def test_sync_applications_returns_error_on_permission_error():
    with patch("tools.sync_applications.get_engine"), \
         patch("services.syncer.WantedClient") as mock_client_cls, \
         patch("tools.sync_applications.JobService"):

        mock_client = MagicMock()
        mock_client.fetch_applications.side_effect = PermissionError("쿠키가 만료되었습니다.")
        mock_client_cls.return_value = mock_client

        from tools.sync_applications import sync_applications
        result = sync_applications()

    assert "쿠키" in result


def test_get_unapplied_jobs_passes_filters():
    with patch("tools.get_unapplied_jobs.get_engine") as mock_engine, \
         patch("tools.get_unapplied_jobs.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.get_unapplied_jobs.return_value = "| 회사명 |..."
        mock_service_cls.return_value = mock_service

        from tools.get_unapplied_jobs import get_unapplied_jobs
        get_unapplied_jobs(location="서울", limit=10)

    mock_service.get_unapplied_jobs.assert_called_once_with(
        job_group_id=None, location="서울", employment_type=None, limit=10
    )


def test_save_preset_returns_error_on_invalid_key():
    with patch("tools.save_search_preset.get_engine"), \
         patch("tools.save_search_preset.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.save_preset.side_effect = ValueError("유효하지 않은 파라미터 키: ['bad']")
        mock_service_cls.return_value = mock_service

        from tools.save_search_preset import save_search_preset
        result = save_search_preset(name="테스트", params={"bad": 1})

    assert "유효하지 않은" in result


from tools.sync_job_details import sync_job_details


def test_sync_job_details_processes_missing():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep") as mock_sleep:

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.upsert_job_details.return_value = "완료: 2개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [
            JobDetail(job_id=101, requirements="req1", preferred_points="pref1", skill_tags=[]),
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        result = sync_job_details()

    assert "2개 처리" in result
    assert mock_client.fetch_job_detail.call_count == 2
    mock_sleep.assert_called_once_with(CRAWL_DELAY_SECONDS)


def test_sync_job_details_skips_failed_fetch():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.upsert_job_details.return_value = "완료: 1개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [
            None,  # 101 실패
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        result = sync_job_details()

    called_details = mock_service.upsert_job_details.call_args[0][0]
    assert len(called_details) == 1
    assert called_details[0].job_id == 102  # 속성 접근


def test_skip_jobs_tool_calls_service():
    with patch("tools.skip_jobs.get_engine"), \
         patch("tools.skip_jobs.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.skip_jobs.return_value = "2개 공고 제외 완료 (사유: 연봉 낮음)"
        MockService.return_value = mock_service

        from tools.skip_jobs import skip_jobs
        result = skip_jobs(job_ids=[101, 102], reason="연봉 낮음")

    mock_service.skip_jobs.assert_called_once_with([101, 102], "연봉 낮음")
    assert "2개 공고 제외 완료" in result


def test_sync_jobs_remember_calls_remember_client():
    with patch("tools.sync_jobs.get_engine"), \
         patch("services.syncer.RememberClient") as MockRememberClient, \
         patch("tools.sync_jobs.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.upsert_jobs.return_value = "동기화 완료: 신규 3개, 변경 0개, 유지 0개"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = []
        MockRememberClient.return_value = mock_client

        from tools.sync_jobs import sync_jobs
        result = sync_jobs(
            source="remember",
            job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
            min_experience=2,
            max_experience=5,
        )

    mock_client.fetch_jobs.assert_called_once_with(
        job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
        min_experience=2,
        max_experience=5,
        limit_pages=DEFAULT_LIMIT_PAGES,
    )
    mock_service.upsert_jobs.assert_called_once_with([], source="remember", full_sync=True)
    mock_service.upsert_remember_details.assert_called_once_with([])


def test_sync_applications_remember_calls_remember_client():
    with patch("tools.sync_applications.get_engine"), \
         patch("services.syncer.RememberClient") as MockRememberClient, \
         patch("tools.sync_applications.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 2건"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_applications.return_value = []
        MockRememberClient.return_value = mock_client

        from tools.sync_applications import sync_applications
        result = sync_applications(source="remember")

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once_with([], source="remember")


def test_get_job_candidates_returns_url():
    from domain import JobCandidate, SkillTag
    from datetime import datetime

    mock_candidate = JobCandidate(
        internal_id=42,
        source=WANTED,
        platform_id=1001,
        company_name="테스트컴퍼니",
        title="Backend Engineer",
        location="서울",
        employment_type="regular",
        requirements="Python req",
        preferred_points=None,
        skill_tags=[SkillTag(text="Python")],
        fetched_at=datetime.now(),
    )

    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = [mock_candidate]
        mock_service.get_recommended_jobs.return_value = [mock_candidate]
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result_str = get_job_candidates(skills=["Python"])

    import json
    result = json.loads(result_str)
    assert "internal_id" not in result[0]
    assert result[0]["url"] == "https://www.wanted.co.kr/wd/1001"


def test_save_job_evaluations_tool_calls_service():
    with patch("tools.save_job_evaluations.get_engine"), \
         patch("tools.save_job_evaluations.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.save_job_evaluations.return_value = "2개 평가 저장 완료"
        MockService.return_value = mock_service

        from tools.save_job_evaluations import save_job_evaluations
        result = save_job_evaluations([
            {"job_id": 1, "verdict": "good"},
            {"job_id": 2, "verdict": "pass"},
        ])

    assert "2개" in result
    mock_service.save_job_evaluations.assert_called_once_with([
        {"job_id": 1, "verdict": "good"},
        {"job_id": 2, "verdict": "pass"},
    ])


def test_save_job_evaluations_tool_returns_error_on_invalid_verdict():
    with patch("tools.save_job_evaluations.get_engine"), \
         patch("tools.save_job_evaluations.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.save_job_evaluations.side_effect = ValueError("유효하지 않은 verdict: ['wrong']")
        MockService.return_value = mock_service

        from tools.save_job_evaluations import save_job_evaluations
        result = save_job_evaluations([{"job_id": 1, "verdict": "wrong"}])

    assert "유효하지 않은" in result


def test_get_job_candidates_includes_job_id():
    from domain import JobCandidate, SkillTag
    from datetime import datetime

    mock_candidate = JobCandidate(
        internal_id=42,
        source="remember",
        platform_id=307222,
        company_name="랭디",
        title="백엔드 개발자",
        location="서울 관악구",
        employment_type=None,
        requirements="Kotlin 필수",
        preferred_points=None,
        skill_tags=[SkillTag(text="백엔드")],
        fetched_at=datetime.now(),
    )

    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = [mock_candidate]
        mock_service.get_recommended_jobs.return_value = [mock_candidate]
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result_str = get_job_candidates(skills=["Kotlin"])

    import json
    result = json.loads(result_str)
    assert result[0]["job_id"] == 42
    assert result[0]["url"] == "https://career.rememberapp.co.kr/job/posting/307222"


def test_get_job_candidates_no_new_jobs_hint():
    """미평가 공고 없을 때 include_evaluated 힌트 메시지를 반환해야 한다."""
    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = []
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result = get_job_candidates(skills=["Python"])

    assert "새로 평가할 공고가 없습니다" in result
    assert "include_evaluated=True" in result


def test_get_job_candidates_passes_include_evaluated():
    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = []
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        get_job_candidates(skills=["Python"], include_evaluated=True)

    mock_service.get_unapplied_job_rows.assert_called_once_with(
        job_group_id=None,
        location=None,
        employment_type=None,
        include_evaluated=True,
    )
