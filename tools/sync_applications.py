from db.connection import get_engine
from services.coupang.coupang_application_syncer import CoupangApplicationSyncer
from services.coupang.coupang_constants import COUPANG
from services.jobs.job_service import JobService
from services.kakaobank.kakaobank_application_syncer import KakaoBankApplicationSyncer
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.naver.naver_constants import NAVER
from services.nhn.nhn_application_syncer import NHNApplicationSyncer
from services.nhn.nhn_constants import NHN
from services.remember.remember_application_syncer import RememberApplicationSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.wanted.wanted_constants import WANTED
from services.woowahan.woowahan_application_syncer import WoowahanApplicationSyncer
from services.woowahan.woowahan_constants import WOOWAHAN


async def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본), REMEMBER, NHN, COUPANG, KAKAO_BANK, WOOWAHAN."""
    engine = get_engine()
    service = JobService(engine)
    if source == REMEMBER:
        return await RememberApplicationSyncer(service).sync()
    if source == NHN:
        return NHNApplicationSyncer(service).sync()
    if source == NAVER:
        return "네이버는 지원현황 API를 지원하지 않습니다."
    if source == COUPANG:
        return CoupangApplicationSyncer(service).sync()
    if source == KAKAO_BANK:
        return KakaoBankApplicationSyncer(service).sync()
    if source == WOOWAHAN:
        return WoowahanApplicationSyncer(service).sync()
    return await WantedApplicationSyncer(service).sync()
