import time

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN


class NHNDetailSyncer(BaseSyncer):
    def sync(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> str:
        try:
            client = NHNClient()
        except ValueError as e:
            return str(e)

        target_ids = self.service.get_jobs_without_details(
            source=NHN, job_ids=job_ids, limit=limit
        )
        if not target_ids:
            return "처리할 공고가 없습니다."

        fetched: list[JobDetail] = []
        for i, job_id in enumerate(target_ids):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw_detail = client.fetch_job_detail(str(job_id))
            if raw_detail is None:
                continue
            parsed = self._parse_nhn_detail(raw_detail)
            fetched.append(JobDetail(
                job_id=job_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=parsed["skill_tags"],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_nhn_detail(raw: dict) -> dict:
        items = raw.get("jobPostingContentsItems") or []
        requirements = None
        preferred_points = None
        for item in items:
            title = item.get("title", "")
            contents = item.get("contents") or []
            text = "\n".join(contents) if contents else None
            if "자격요건" in title:
                requirements = text
            elif "우대사항" in title:
                preferred_points = text

        seen_ids: set = set()
        skill_tags: list[dict] = []
        for series in (raw.get("jobSeries") or []):
            sid = series.get("id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                skill_tags.append({"text": series["name"]})

        return {
            "requirements": requirements,
            "preferred_points": preferred_points,
            "skill_tags": skill_tags,
        }
