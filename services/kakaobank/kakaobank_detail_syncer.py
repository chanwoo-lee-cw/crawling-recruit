import time
from bs4 import BeautifulSoup
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=KAKAO_BANK, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = KakaoBankClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw_detail = client.fetch_job_detail(int(platform_id))
            if raw_detail is None:
                continue
            contents_html = raw_detail.get("contents") or ""
            parsed = self._parse_kakaobank_detail(contents_html)
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
    def _parse_kakaobank_detail(html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        requirements = None
        preferred_points = None

        for block in soup.select("div.desc_cont"):
            tit_tag = block.select_one("div.tit")
            tit_text = tit_tag.get_text(strip=True) if tit_tag else ""
            cont_tag = block.select_one("div.cont")
            if not cont_tag:
                continue
            text = "\n".join(
                p.get_text(strip=True) for p in cont_tag.find_all("p") if p.get_text(strip=True)
            ) or None

            if "필수 경험과 역량" in tit_text:
                requirements = text
            elif "우대사항" in tit_text:
                preferred_points = text

        return {"requirements": requirements, "preferred_points": preferred_points, "skill_tags": []}
