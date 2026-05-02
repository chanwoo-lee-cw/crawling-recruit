import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN


class WoowahanDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=WOOWAHAN, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = WoowahanClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            recruit_number = f"R{platform_id}"
            raw_detail = client.fetch_job_detail(recruit_number)
            if raw_detail is None:
                continue
            contents_html = raw_detail.get("recruitContents") or ""
            parsed = self._parse_woowahan_detail(contents_html)
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
    def _parse_woowahan_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        current_section = None
        section_lines: dict[str, list[str]] = {"requirements": [], "preferred_points": []}

        for elem in soup.find_all(["strong", "p"]):
            if elem.name == "strong":
                text = elem.get_text(strip=True)
                if "[지원자격]" in text:
                    current_section = "requirements"
                elif "[우대사항]" in text:
                    current_section = "preferred_points"
                else:
                    current_section = None
            elif elem.name == "p" and current_section:
                if elem.find("strong"):
                    continue
                text = elem.get_text(strip=True)
                if text:
                    section_lines[current_section].append(text)

        requirements = "\n".join(section_lines["requirements"]) or None
        preferred_points = "\n".join(section_lines["preferred_points"]) or None

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
