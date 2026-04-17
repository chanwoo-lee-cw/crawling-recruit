import pytest
from unittest.mock import patch, MagicMock
from domain import JobDetail


def test_sync_jobs_uses_preset_when_given():
    with patch("tools.sync_jobs.get_engine") as mock_engine, \
         patch("tools.sync_jobs.WantedClient") as mock_client_cls, \
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
    call_kwargs = mock_client.fetch_jobs.call_args.kwargs
    assert call_kwargs.get("job_group_id") == 519


def test_sync_applications_returns_error_on_permission_error():
    with patch("tools.sync_applications.get_engine"), \
         patch("tools.sync_applications.WantedClient") as mock_client_cls, \
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
    mock_sleep.assert_called_once_with(1)


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
