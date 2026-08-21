import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.sk.sk_client import SKClient
from services.sk.sk_constants import SK


class SKDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=SK, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = SKClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_detail_html(html)
            fetched.append(JobDetail(
                job_id=internal_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=[],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_detail_html(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for section in soup.select("div.detail-content-item"):
            h3 = section.select_one("h3.detail-content-title")
            if not h3:
                continue
            h3_text = h3.get_text(strip=True)
            items = [li.get_text(strip=True) for li in section.select("ul.asset-list li") if li.get_text(strip=True)]
            text = "\n".join(items) or None
            # SK는 같은 페이지를 한국어/영문 제목으로 모두 내려준다
            h3_lower = h3_text.lower()
            if "함께 하고 싶" in h3_text or "looking for" in h3_lower:
                requirements = text
            elif "경험이 있다면" in h3_text or "preferred" in h3_lower:
                preferred_points = text

        return {"requirements": requirements, "preferred_points": preferred_points}
