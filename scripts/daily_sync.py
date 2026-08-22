import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from services.cj.cj_constants import CJ
from services.coupang.coupang_constants import COUPANG
from services.kakaobank.kakaobank_constants import KAKAO_BANK
from services.kt.kt_constants import KT
from services.naver.naver_constants import NAVER
from services.nhn.nhn_constants import NHN
from services.remember.remember_constants import REMEMBER, RememberJobCategory
from services.samsung.samsung_constants import SAMSUNG
from services.sk.sk_constants import SK
from services.wanted.wanted_constants import WANTED, WantedJobSort
from services.woowahan.woowahan_constants import WOOWAHAN
from tools.cj_sync_jobs import cj_sync_jobs
from tools.coupang_sync_jobs import coupang_sync_jobs
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs
from tools.kt_sync_jobs import kt_sync_jobs
from tools.naver_sync_jobs import naver_sync_jobs
from tools.nhn_sync_jobs import nhn_sync_jobs
from tools.remember_sync_jobs import remember_sync_jobs
from tools.samsung_sync_jobs import samsung_sync_jobs
from tools.sk_sync_jobs import sk_sync_jobs
from tools.sync_applications import sync_applications
from tools.sync_job_details import sync_job_details
from tools.wanted_sync_jobs import wanted_sync_jobs
from tools.woowahan_sync_jobs import woowahan_sync_jobs

SOURCES = [
    NHN,
    WANTED,
    REMEMBER,
    NAVER,
    COUPANG,
    KAKAO_BANK,
    WOOWAHAN,
    CJ,
    KT,
    SAMSUNG,
    SK,
]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(_PROJECT_ROOT, "logs"), exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def run():
    log("=== daily sync start ===")

    synced_count = 0
    for source in SOURCES:
        try:
            if source == WANTED:
                await wanted_sync()
            elif source == REMEMBER:
                await remember_sync()
            elif source == NHN:
                nhn_sync()
            elif source == NAVER:
                naver_sync()
            elif source == COUPANG:
                coupang_sync()
            elif source == KAKAO_BANK:
                kakaobank_sync()
            elif source == WOOWAHAN:
                woowahan_sync()
            elif source == CJ:
                await cj_sync()
            elif source == KT:
                await kt_sync()
            elif source == SAMSUNG:
                await samsung_sync()
            elif source == SK:
                await sk_sync()
            else:
                raise RuntimeError(f"정의되지 않은 source[{source}] 입니다.")
            synced_count += 1
        except Exception as e:
            log(f"sync_jobs({source}): 오류 - {e}")

    if synced_count == 0:
        log("모든 sync_jobs 실패 - sync_job_details 스킵")
    else:
        for src in SOURCES:
            try:
                result = await sync_job_details(source=src)
                log(f"sync_job_details({src}): {result}")
            except Exception as e:
                log(f"sync_job_details({src}): 오류 - {e}")

    for source in SOURCES:
        try:
            result = await sync_applications(source=source)
            log(f"sync_applications({source}): {result}")
        except Exception as e:
            log(f"sync_applications({source}): 오류 - {e}")

    log("=== daily sync end ===")


async def wanted_sync():
    for sort in WantedJobSort:
        try:
            result = await wanted_sync_jobs(job_sort=sort.value)
            log(f"wanted_sync_jobs({sort.name}): {result}")
        except Exception as e:
            log(f"wanted_sync_jobs({sort.name}): 오류 - {e}")


async def remember_sync():
    try:
        result = await remember_sync_jobs(
            job_category_names=[cat.payload for cat in RememberJobCategory]
        )
        log(f"remember_sync_jobs: {result}")
    except Exception as e:
        log(f"remember_sync_jobs: 오류 - {e}")
        
        
def nhn_sync():
    try:
        result = nhn_sync_jobs()
        log(f"nhn_sync_jobs: {result}")
    except Exception as e:
        log(f"nhn_sync_jobs: 오류 - {e}")


def naver_sync():
    try:
        result = naver_sync_jobs()
        log(f"naver_sync_jobs: {result}")
    except Exception as e:
        log(f"naver_sync_jobs: 오류 - {e}")


def coupang_sync():
    try:
        result = coupang_sync_jobs()
        log(f"coupang_sync_jobs: {result}")
    except Exception as e:
        log(f"coupang_sync_jobs: 오류 - {e}")


def kakaobank_sync():
    try:
        result = kakaobank_sync_jobs()
        log(f"kakaobank_sync_jobs: {result}")
    except Exception as e:
        log(f"kakaobank_sync_jobs: 오류 - {e}")


def woowahan_sync():
    try:
        result = woowahan_sync_jobs()
        log(f"woowahan_sync_jobs: {result}")
    except Exception as e:
        log(f"woowahan_sync_jobs: 오류 - {e}")


async def cj_sync():
    try:
        result = await cj_sync_jobs()
        log(f"cj_sync_jobs: {result}")
    except Exception as e:
        log(f"cj_sync_jobs: 오류 - {e}")


async def kt_sync():
    try:
        result = await kt_sync_jobs()
        log(f"kt_sync_jobs: {result}")
    except Exception as e:
        log(f"kt_sync_jobs: 오류 - {e}")


async def samsung_sync():
    try:
        result = await samsung_sync_jobs()
        log(f"samsung_sync_jobs: {result}")
    except Exception as e:
        log(f"samsung_sync_jobs: 오류 - {e}")


async def sk_sync():
    try:
        result = await sk_sync_jobs()
        log(f"sk_sync_jobs: {result}")
    except Exception as e:
        log(f"sk_sync_jobs: 오류 - {e}")


if __name__ == "__main__":
    asyncio.run(run())
