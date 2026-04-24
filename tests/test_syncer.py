import pytest
from unittest.mock import patch, MagicMock
from services.base_syncer import BaseSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_syncer import WantedSyncer
from services.remember.remember_syncer import RememberSyncer
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.remember.remember_application_syncer import RememberApplicationSyncer


def test_base_syncer_is_abstract():
    with pytest.raises(TypeError):
        BaseSyncer(service=MagicMock())


def test_wanted_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_jobs.return_value = "동기화 완료: 신규 2개, 변경 0개, 유지 0개"

    with patch("services.wanted.wanted_syncer.WantedClient") as MockClient:
        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = [{"id": 1}, {"id": 2}]
        MockClient.return_value = mock_client

        syncer = WantedSyncer(mock_service)
        result = syncer.sync(
            job_group_id=518, job_ids=None, years=None,
            locations="all", limit_pages=2, job_sort="job.popularity_order",
        )

    mock_client.fetch_jobs.assert_called_once_with(
        job_group_id=518, job_ids=None, years=None,
        locations="all", limit_pages=2, job_sort="job.popularity_order",
    )
    mock_service.upsert_jobs.assert_called_once()
    assert "동기화 완료" in result


def test_remember_syncer_calls_client_upsert_and_details():
    mock_service = MagicMock()
    mock_service.upsert_jobs.return_value = "동기화 완료: 신규 1개, 변경 0개, 유지 0개"

    with patch("services.remember.remember_syncer.RememberClient") as MockClient:
        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = [{"id": 10}]
        MockClient.return_value = mock_client

        syncer = RememberSyncer(mock_service)
        result = syncer.sync(
            job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
            min_experience=0, max_experience=5, limit_pages=None,
        )

    mock_client.fetch_jobs.assert_called_once()
    mock_service.upsert_jobs.assert_called_once_with([{"id": 10}], source=REMEMBER, full_sync=True)
    mock_service.upsert_remember_details.assert_called_once_with([{"id": 10}])
    assert "동기화 완료" in result


def test_remember_syncer_returns_error_without_job_categories():
    syncer = RememberSyncer(service=MagicMock())
    result = syncer.sync(job_category_names=None, min_experience=0, max_experience=5, limit_pages=None)
    assert "job_category_names" in result


def test_wanted_application_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 3건"

    with patch("services.wanted.wanted_application_syncer.WantedClient") as MockClient:
        mock_client = MagicMock()
        mock_client.fetch_applications.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        MockClient.return_value = mock_client

        syncer = WantedApplicationSyncer(mock_service)
        result = syncer.sync()

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once()
    assert "3건" in result


def test_wanted_application_syncer_returns_error_on_permission_error():
    mock_service = MagicMock()

    with patch("services.wanted.wanted_application_syncer.WantedClient") as MockClient:
        MockClient.return_value.fetch_applications.side_effect = PermissionError("쿠키가 만료되었습니다.")

        syncer = WantedApplicationSyncer(mock_service)
        result = syncer.sync()

    assert "쿠키" in result


def test_remember_application_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 2건"

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        mock_client = MagicMock()
        mock_client.fetch_applications.return_value = [{"id": 10}, {"id": 11}]
        MockClient.return_value = mock_client

        syncer = RememberApplicationSyncer(mock_service)
        result = syncer.sync()

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once_with([{"id": 10}, {"id": 11}], source=REMEMBER)
    assert "2건" in result


def test_remember_application_syncer_returns_error_on_permission_error():
    mock_service = MagicMock()

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        MockClient.return_value.fetch_applications.side_effect = PermissionError("Remeber 쿠키 만료")

        syncer = RememberApplicationSyncer(mock_service)
        result = syncer.sync()

    assert "쿠키" in result


def test_remember_application_syncer_catches_generic_exception():
    mock_service = MagicMock()

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        MockClient.return_value.fetch_applications.side_effect = RuntimeError("네트워크 오류")

        syncer = RememberApplicationSyncer(mock_service)
        result = syncer.sync()

    assert "오류" in result
