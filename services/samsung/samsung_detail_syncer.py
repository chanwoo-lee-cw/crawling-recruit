import time
from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.samsung.samsung_client import SamsungClient
from services.samsung.samsung_constants import SAMSUNG


class SamsungDetailSyncer(BaseSyncer):
    def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        target_pairs = self.service.get_jobs_without_details(
            source=SAMSUNG, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        client = SamsungClient()
        fetched: list[JobDetail] = []
        for i, (internal_id, platform_id) in enumerate(target_pairs):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw = client.fetch_job_detail(int(platform_id))
            if raw is None:
                continue
            parsed = self._parse_detail(raw)
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
    def _parse_detail(data: dict) -> dict:
        result = data.get("result") or {}
        items = data.get("items") or []

        req_parts = []
        if result.get("qlfctKr"):
            req_parts.append(result["qlfctKr"])
        for item in items:
            title = item.get("titleKr", "")
            qlfct = (item.get("qlfctKr") or "").strip()
            if qlfct:
                req_parts.append(f"[{title}]\n{qlfct}" if title else qlfct)

        favor_parts = []
        for item in items:
            title = item.get("titleKr", "")
            favor = (item.get("favorKr") or "").strip()
            if favor:
                favor_parts.append(f"[{title}]\n{favor}" if title else favor)

        return {
            "requirements": "\n\n".join(req_parts) or None,
            "preferred_points": "\n\n".join(favor_parts) or None,
        }
