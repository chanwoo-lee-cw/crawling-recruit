from unittest.mock import MagicMock, patch
from services.naver.naver_syncer import NaverSyncer
from services.naver.naver_constants import NAVER

MOCK_JOBS = [{"annoId": 30004786, "sysCompanyCdNm": "NAVER", "annoSubject": "백엔드", "empTypeCdNm": "정규", "subJobCdNm": "Backend"}]


def test_syncer_calls_upsert_with_full_sync_true_when_no_limit():
    service = MagicMock()
    with patch("services.naver.naver_syncer.NaverClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = MOCK_JOBS
        NaverSyncer(service).sync(limit_pages=None)
    service.upsert_jobs.assert_called_once_with(MOCK_JOBS, source=NAVER, full_sync=True)


def test_syncer_calls_upsert_with_full_sync_false_when_limit_set():
    service = MagicMock()
    syncer = NaverSyncer.__new__(NaverSyncer)
    syncer.service = service
    with patch("services.naver.naver_syncer.NaverClient") as MockClient:
        MockClient.return_value.fetch_jobs.return_value = MOCK_JOBS
        syncer.sync(limit_pages=2)
    service.upsert_jobs.assert_called_once_with(MOCK_JOBS, source=NAVER, full_sync=False)
