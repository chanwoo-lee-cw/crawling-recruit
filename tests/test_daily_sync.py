from unittest.mock import patch, call

from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_constants import WANTED


def test_run_calls_sync_jobs_for_each_source():
    """SOURCES의 각 소스에 대해 sync_jobs가 호출되는지 확인"""
    with patch("scripts.daily_sync.sync_jobs") as mock_sync_jobs, \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        mock_sync_jobs.return_value = "동기화 완료: 10개"
        mock_details.return_value = "상세 10개 수집"
        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        run()

    assert mock_sync_jobs.call_count == 2
    calls = mock_sync_jobs.call_args_list
    assert calls[0] == call(source=WANTED)
    assert calls[1] == call(
        source=REMEMBER,
        job_category_names=[{"name": "백엔드 개발자"}, {"name": "서버 개발자"}],
    )
    mock_details.assert_called_once()
    assert mock_apps.call_count == 2  # wanted + remember


def test_run_skips_job_details_if_all_sync_jobs_fail():
    """모든 sync_jobs가 실패하면 sync_job_details를 실행하지 않는다"""
    with patch("scripts.daily_sync.sync_jobs", side_effect=Exception("API 오류")), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_not_called()


def test_run_continues_after_sync_jobs_partial_failure():
    """일부 sync_jobs가 실패해도 성공한 소스가 있으면 sync_job_details를 실행한다"""
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("wanted 오류")
        return "동기화 완료: 5개"

    with patch("scripts.daily_sync.sync_jobs", side_effect=side_effect), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications"):

        from scripts.daily_sync import run
        run()

    mock_details.assert_called_once()


def test_run_continues_after_sync_job_details_failure():
    """sync_job_details가 실패해도 sync_applications는 실행된다"""
    with patch("scripts.daily_sync.sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", side_effect=Exception("상세 오류")), \
         patch("scripts.daily_sync.sync_applications") as mock_apps:

        from scripts.daily_sync import run
        run()

    assert mock_apps.call_count >= 1
