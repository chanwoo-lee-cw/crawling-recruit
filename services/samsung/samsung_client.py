import time
import httpx
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from services.samsung.samsung_constants import SAMSUNG_LIST_URL, SAMSUNG_DETAIL_URL


class SamsungClient:
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(SAMSUNG_LIST_URL, headers=self._HEADERS, timeout=30)
        resp.raise_for_status()
        return self._parse_list_html(resp.text)

    @staticmethod
    def _parse_list_html(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        for li in soup.select("li"):
            a_tag = li.select_one("a[data-value]")
            if not a_tag:
                continue
            raw_id = a_tag.get("data-value", "").replace(",", "").strip()
            if not raw_id.isdigit():
                continue
            company_tag = li.select_one("p.company")
            title_tag = li.select_one("h3.title")
            info_tag = li.select_one("p.info")
            emp_span = None
            if info_tag:
                emp_span = info_tag.find("span", class_=False)
                if emp_span is None:
                    emp_span = info_tag.find("span")
            jobs.append({
                "id": int(raw_id),
                "company": company_tag.get_text(strip=True) if company_tag else "삼성",
                "title": title_tag.get_text(strip=True) if title_tag else "",
                "employment_type": emp_span.get_text(strip=True) if emp_span else None,
            })
        return jobs

    def fetch_job_detail(self, platform_id: int) -> dict | None:
        try:
            resp = httpx.get(
                SAMSUNG_DETAIL_URL,
                params={"seqno": platform_id, "strCode": ""},
                headers=self._HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception:
            return None
