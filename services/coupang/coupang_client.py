import logging
import httpx
from bs4 import BeautifulSoup
from services.coupang.coupang_constants import (
    COUPANG_LIST_URL, COUPANG_DETAIL_BASE_URL, COUPANG_PAGE_SIZE
)

logger = logging.getLogger(__name__)


class CoupangClient:
    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(
            COUPANG_LIST_URL,
            params={"search": "", "location": "South+Korea", "pagesize": COUPANG_PAGE_SIZE},
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in soup.select("div.card.card-job"):
            actions = card.select_one("div.card-job-actions.js-job")
            if not actions:
                continue
            job_id = actions.get("data-id")
            title_tag = card.select_one("h2.card-title a.js-view-job")
            title = title_tag.get_text(strip=True) if title_tag else ""
            location_tag = card.select_one("ul.list-inline li.list-inline-item")
            location = location_tag.get_text(strip=True) if location_tag else None
            if job_id and title:
                jobs.append({"id": int(job_id), "title": title, "location": location})
        if len(jobs) >= COUPANG_PAGE_SIZE:
            logger.warning("Coupang: job count >= %d, consider adding pagination", COUPANG_PAGE_SIZE)
        return jobs

    def fetch_job_detail(self, job_id: int) -> str | None:
        try:
            resp = httpx.get(f"{COUPANG_DETAIL_BASE_URL}/{job_id}", timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
