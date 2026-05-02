from unittest.mock import patch, AsyncMock

from services.coupang.coupang_constants import COUPANG
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.nhn.nhn_constants import NHN
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_constants import WANTED, WantedJobSort
from services.woowahan.woowahan_constants import WOOWAHAN


def _all_sync_patches(extra=None):
    patches = {
        "scripts.daily_sync.wanted_sync_jobs": "완료",
        "scripts.daily_sync.remember_sync_jobs": "완료",
        "scripts.daily_sync.nhn_sync_jobs": "완료",
        "scripts.daily_sync.naver_sync_jobs": "완료",
        "scripts.daily_sync.coupang_sync_jobs": "완료",
        "scripts.daily_sync.kakaobank_sync_jobs": "완료",
        "scripts.daily_sync.woowahan_sync_jobs": "완료",
        "scripts.daily_sync.sync_job_details": "완료",
        "scripts.daily_sync.sync_applications": "완료",
    }
    if extra:
        patches.update(extra)
    return patches


async def test_run_calls_wanted_sync_jobs_for_each_sort():
    """wanted_sync_jobs가 WantedJobSort 종류만큼 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", new_callable=AsyncMock) as mock_wanted, \
         patch("scripts.daily_sync.remember_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.nhn_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.naver_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.coupang_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.woowahan_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", return_value="완료"), \
         patch("scripts.daily_sync.sync_applications", new_callable=AsyncMock, return_value="완료"):

        mock_wanted.return_value = "동기화 완료: 10개"

        from scripts.daily_sync import run
        await run()

    assert mock_wanted.call_count == len(WantedJobSort)
    for sort in WantedJobSort:
        mock_wanted.assert_any_call(job_sort=sort.value)


async def test_run_calls_sync_job_details_for_each_source():
    """sync_job_details는 각 source별로 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.nhn_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.naver_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.coupang_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.woowahan_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications", new_callable=AsyncMock, return_value="완료"):

        from scripts.daily_sync import run
        await run()

    sources = [c.kwargs["source"] for c in mock_details.call_args_list]
    assert NHN in sources
    assert WANTED in sources
    assert REMEMBER in sources
    assert COUPANG in sources
    assert KAKAO_BANK in sources
    assert WOOWAHAN in sources


async def test_run_calls_sync_applications_for_each_source():
    """sync_applications는 각 source별로 호출된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.nhn_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.naver_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.coupang_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.woowahan_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", return_value="완료"), \
         patch("scripts.daily_sync.sync_applications", new_callable=AsyncMock) as mock_apps:

        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        await run()

    sources = [c.kwargs["source"] for c in mock_apps.call_args_list]
    assert NHN in sources
    assert WANTED in sources
    assert REMEMBER in sources
    assert COUPANG in sources
    assert KAKAO_BANK in sources
    assert WOOWAHAN in sources


async def test_run_continues_after_wanted_sync_jobs_failure():
    """wanted_sync_jobs 일부가 실패해도 다른 sync와 sync_job_details가 실행된다"""
    async def wanted_side_effect(**kwargs):
        if kwargs.get("job_sort") == WantedJobSort.LATEST_ORDER.value:
            raise Exception("API 오류")
        return "동기화 완료: 5개"

    with patch("scripts.daily_sync.wanted_sync_jobs", side_effect=wanted_side_effect), \
         patch("scripts.daily_sync.remember_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.nhn_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.naver_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.coupang_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.woowahan_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details") as mock_details, \
         patch("scripts.daily_sync.sync_applications", new_callable=AsyncMock, return_value="완료"):

        from scripts.daily_sync import run
        await run()

    assert mock_details.call_count >= 1


async def test_run_continues_after_sync_job_details_failure():
    """sync_job_details가 실패해도 sync_applications는 실행된다"""
    with patch("scripts.daily_sync.wanted_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.remember_sync_jobs", new_callable=AsyncMock, return_value="완료"), \
         patch("scripts.daily_sync.nhn_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.naver_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.coupang_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.kakaobank_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.woowahan_sync_jobs", return_value="완료"), \
         patch("scripts.daily_sync.sync_job_details", side_effect=Exception("상세 오류")), \
         patch("scripts.daily_sync.sync_applications", new_callable=AsyncMock) as mock_apps:

        mock_apps.return_value = "완료"

        from scripts.daily_sync import run
        await run()

    assert mock_apps.call_count >= 1
