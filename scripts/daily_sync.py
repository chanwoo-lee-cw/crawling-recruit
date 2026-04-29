import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from services.nhn.nhn_constants import NHN
from tools.nhn_sync_jobs import nhn_sync_jobs
from services.remember.remember_constants import REMEMBER, RememberJobCategory
from services.wanted.wanted_constants import WANTED, WantedJobSort
from tools.remember_sync_jobs import remember_sync_jobs
from tools.wanted_sync_jobs import wanted_sync_jobs

from tools.sync_job_details import sync_job_details
from tools.sync_applications import sync_applications

SOURCES = [
    NHN,
    WANTED,
    REMEMBER
]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(_PROJECT_ROOT, "logs"), exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run():
    log("=== daily sync start ===")

    synced_count = 0
    for source in SOURCES:
        try:
            if source == WANTED:
                wanted_sync()
            elif source == REMEMBER:
                remember_sync()
            elif source == NHN:
                nhn_sync()
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
                result = sync_job_details(source=src)
                log(f"sync_job_details({src}): {result}")
            except Exception as e:
                log(f"sync_job_details({src}): 오류 - {e}")

    for source in SOURCES:
        try:
            result = sync_applications(source=source)
            log(f"sync_applications({source}): {result}")
        except Exception as e:
            log(f"sync_applications({source}): 오류 - {e}")

    log("=== daily sync end ===")


def wanted_sync():
    for sort in WantedJobSort:
        try:
            result = wanted_sync_jobs(job_sort=sort.value)
            log(f"wanted_sync_jobs({sort.name}): {result}")
        except Exception as e:
            log(f"wanted_sync_jobs({sort.name}): 오류 - {e}")


def remember_sync():
    try:
        result = remember_sync_jobs(
            job_category_names=[{"name": cat.value} for cat in RememberJobCategory]
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



if __name__ == "__main__":
    run()
