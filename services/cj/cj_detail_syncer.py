import time

from bs4 import BeautifulSoup

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.cj.cj_client import CJClient
from services.cj.cj_constants import CJ
from services.html_text import to_lines

# 직무소개에는 사용 기술과 업무 범위가 적혀 있어 매칭에 쓸모가 있다.
_REQUIREMENT_SECTIONS = ("지원자격", "자격요건", "필수요건", "직무소개")
_PREFERRED_SECTIONS = ("우대사항", "우대요건")


class CJDetailSyncer(BaseSyncer):
    async def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=CJ, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = CJClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            html = client.fetch_job_detail(int(platform_id))
            if html is None:
                continue
            parsed = self._parse_detail_html(html)
            if parsed["requirements"] is None and parsed["preferred_points"] is None:
                continue
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
        """상세 페이지는 <li> 안에 <h3>섹션명</h3> + 본문 구조로 되어 있다."""
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one("div.detail") or soup
        requirements: list[str] = []
        preferred: list[str] = []

        for heading in container.find_all("h3"):
            name = heading.get_text(strip=True)
            section = heading.parent
            if section is None:
                continue
            heading.extract()  # 제목을 떼어내고 남은 내용만 본문으로
            body = "\n".join(to_lines(section))
            if not body:
                continue
            if name.startswith(_REQUIREMENT_SECTIONS):
                requirements.append(body)
            elif name.startswith(_PREFERRED_SECTIONS):
                preferred.append(body)

        return {
            "requirements": "\n".join(requirements) or None,
            "preferred_points": "\n".join(preferred) or None,
        }
