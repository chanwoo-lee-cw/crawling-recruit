import pytest
from unittest.mock import patch, call, AsyncMock

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


def test_remember_job_category_payload_uses_level_pairs():
    """리멤버 API는 {'name': ...}가 아니라 {'level1','level2'} 쌍으로 필터링한다.

    매칭되는 카테고리가 없으면 필터를 통째로 무시하고 전 직군을 반환해서,
    마케팅·영업 공고까지 수집되고 있었다. (docs/리멤버_type.md)
    """
    from services.remember.remember_constants import RememberJobCategory
    payloads = [cat.payload for cat in RememberJobCategory]
    assert all(set(p) == {"level1", "level2"} for p in payloads)
    assert {"level1": "SW개발", "level2": "백엔드"} in payloads


@pytest.mark.asyncio
async def test_daily_sync_remember_passes_level_pairs():
    from services.remember.remember_constants import RememberJobCategory
    with patch("scripts.daily_sync.remember_sync_jobs", new=AsyncMock(return_value="완료")) as mock_sync:
        from scripts.daily_sync import remember_sync
        await remember_sync()
    sent = mock_sync.call_args.kwargs["job_category_names"]
    assert sent == [cat.payload for cat in RememberJobCategory]
    assert all("name" not in p for p in sent)
