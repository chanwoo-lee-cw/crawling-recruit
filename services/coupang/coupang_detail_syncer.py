import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.coupang.coupang_client import CoupangClient
from services.coupang.coupang_constants import COUPANG


class CoupangDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=COUPANG, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = CoupangClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_coupang_detail(html)
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
    def _parse_coupang_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        article = soup.select_one("div.main-col article.cms-content")
        requirements = None
        preferred_points = None

        if article:
            current_section = None
            section_lines: dict[str, list[str]] = {"requirements": [], "preferred_points": []}

            for elem in article.find_all(["strong", "li"]):
                if elem.name == "strong":
                    text = elem.get_text(strip=True)
                    if "자격 요건" in text:
                        current_section = "requirements"
                    elif "우대 사항" in text:
                        current_section = "preferred_points"
                    else:
                        current_section = None
                elif elem.name == "li" and current_section:
                    li_text = elem.get_text(strip=True)
                    if li_text:
                        section_lines[current_section].append(li_text)

            requirements = "\n".join(section_lines["requirements"]) or None
            preferred_points = "\n".join(section_lines["preferred_points"]) or None

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
