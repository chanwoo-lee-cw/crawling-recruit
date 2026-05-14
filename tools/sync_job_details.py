from db.connection import get_engine
from services.cj.cj_constants import CJ
from services.cj.cj_detail_syncer import CJDetailSyncer
from services.coupang.coupang_constants import COUPANG
from services.coupang.coupang_detail_syncer import CoupangDetailSyncer
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer
from services.kt.kt_constants import KT
from services.kt.kt_detail_syncer import KTDetailSyncer
from services.naver.naver_constants import NAVER
from services.naver.naver_detail_syncer import NaverDetailSyncer
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_detail_syncer import RememberDetailSyncer
from services.samsung.samsung_constants import SAMSUNG
from services.samsung.samsung_detail_syncer import SamsungDetailSyncer
from services.sk.sk_constants import SK
from services.sk.sk_detail_syncer import SKDetailSyncer
from services.wanted.wanted_constants import WANTED
from services.wanted.wanted_detail_syncer import WantedDetailSyncer
from services.woowahan.woowahan_constants import WOOWAHAN
from services.woowahan.woowahan_detail_syncer import WoowahanDetailSyncer


async def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: WANTED (기본), REMEMBER, NHN, NAVER, COUPANG, KAKAO_BANK, WOOWAHAN."""
    service = JobService(get_engine())
    if source == CJ:
        return await CJDetailSyncer(service).sync()
    if source == KT:
        return await KTDetailSyncer(service).sync()
    if source == SAMSUNG:
        return SamsungDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == SK:
        return SKDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == NAVER:
        return NaverDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == COUPANG:
        return CoupangDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == KAKAO_BANK:
        return KakaoBankDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    if source == WOOWAHAN:
        return WoowahanDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return await WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)


if __name__ == "__main__":
    sync_job_details(NHN)
