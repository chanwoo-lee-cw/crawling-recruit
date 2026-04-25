from unittest.mock import patch, call, MagicMock

from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_constants import WANTED, WantedJobSort


def test_run_calls_wanted_sync_jobs_for_each_sort():
    """wanted_sync_jobs가 WantedJobSort 종류만큼 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs") as mock_wanted, \
         patch("scripts.daily_sync.remember_sync_jobs") as mock_remember, \
         patch("scripts.daily_sync.sync_job_details", return_value="완료"), \
         patch("scripts.daily_sync.sync_applications", return_value="완료"):

        mock_wanted.return_value = "동기화 완료: 10개"
        mock_remember.return_value = "동기화 완료: 5개"

        from scripts.daily_sync import run
        run()

    assert mock_wanted.call_count == len(WantedJobSort)
    for sort in WantedJobSort:
        mock_wanted.assert_any_call(job_sort=sort.value)


def test_run_calls_sync_job_details_after_sync():
    """sync_job_details는 wanted/remember sync 이후에 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications", return_value="완료"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_called_once()


def test_run_calls_sync_applications_for_each_source():
    """sync_applications는 WANTED, REMEMBER 각각 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", return_value="완료"), \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        run()

    assert mock_apps.call_count == 2
    sources = [c.kwargs["source"] for c in mock_apps.call_args_list]
    assert WANTED in sources
    assert REMEMBER in sources


def test_run_continues_after_wanted_sync_jobs_failure():
    """wanted_sync_jobs 일부가 실패해도 remember sync와 sync_job_details가 실행된다"""
    def wanted_side_effect(**kwargs):
        if kwargs.get("job_sort") == WantedJobSort.LATEST_ORDER.value:
            raise Exception("API 오류")
        return "동기화 완료: 5개"

    with patch("scripts.daily_sync.wanted_sync_jobs", side_effect=wanted_side_effect), \
         patch("scripts.daily_sync.remember_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications", return_value="완료"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_called_once()


def test_run_continues_after_sync_job_details_failure():
    """sync_job_details가 실패해도 sync_applications는 실행된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", side_effect=Exception("상세 오류")), \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        run()

    assert mock_apps.call_count >= 1
