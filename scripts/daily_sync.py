import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from tools.sync_jobs import sync_jobs
from tools.sync_job_details import sync_job_details
from tools.sync_applications import sync_applications

SOURCES = ["wanted", "remember"]

SYNC_CONFIG = {
    "wanted": {},
    "remember": {
        "job_category_names": [
            {"name": "백엔드 개발자"},
            {"name": "서버 개발자"},
        ],
    },
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run():
    log("=== daily sync start ===")

    synced_count = 0
    for source in SOURCES:
        try:
            kwargs = SYNC_CONFIG.get(source, {})
            result = sync_jobs(source=source, **kwargs)
            log(f"sync_jobs({source}): {result}")
            synced_count += 1
        except Exception as e:
            log(f"sync_jobs({source}): 오류 - {e}")

    if synced_count == 0:
        log("모든 sync_jobs 실패 - sync_job_details 스킵")
    else:
        try:
            result = sync_job_details()
            log(f"sync_job_details: {result}")
        except Exception as e:
            log(f"sync_job_details: 오류 - {e}")

    for source in SOURCES:
        try:
            result = sync_applications(source=source)
            log(f"sync_applications({source}): {result}")
        except Exception as e:
            log(f"sync_applications({source}): 오류 - {e}")

    log("=== daily sync end ===")


if __name__ == "__main__":
    run()
