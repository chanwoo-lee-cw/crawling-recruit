import time

from bs4 import BeautifulSoup

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.naver.naver_client import NaverClient
from services.naver.naver_constants import NAVER


class NaverDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=NAVER, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = NaverClient()
        fetched: list[JobDetail] = []

        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_naver_detail(html)
            fetched.append(JobDetail(
                job_id=internal_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=parsed["skill_tags"],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_naver_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for box in soup.select("div.detail_box"):
            title_tag = box.find("h4", class_="detail_title")
            title_text = title_tag.get_text(strip=True) if title_tag else ""
            text_tag = box.find("p", class_="detail_text")
            text = text_tag.get_text(separator="\n", strip=True) if text_tag else ""

            if "자격요건" in title_text:
                requirements = text or None
            elif "우대사항" in title_text:
                preferred_points = text or None

        if requirements is None and preferred_points is None:
            wrap = soup.select_one("div.detail_wrap")
            if wrap:
                fallback = wrap.get_text(separator="\n", strip=True)
                requirements = fallback or None

        return {
            "requirements": requirements,
            "preferred_points": preferred_points,
            "skill_tags": [],
        }
