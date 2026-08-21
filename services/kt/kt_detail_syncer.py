import re

from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.html_text import to_lines
from services.kt.kt_client import KTClient
from services.kt.kt_constants import KT, extract_kt_platform_id

_MARKERS = "●○■□▶▪◆◇★☆✓✔☑√※"
_HEADING_PREFIX = re.compile(rf"^[\s{_MARKERS}•*\-–\[\(]+|[\]\):]+$")
_SECTION_MARKER = re.compile(rf"^\s*[{_MARKERS}]")
_REQUIREMENT_HEADINGS = ("필수요건", "자격요건", "지원자격", "필수자격", "자격 요건", "지원 자격", "필수 요건", "필수 자격")
_PREFERRED_HEADINGS = ("우대사항", "우대요건", "우대 사항", "우대 요건")


class KTDetailSyncer(BaseSyncer):
    async def sync(self, job_ids: list[int] | None = None, limit: int | None = None) -> str:
        """KT 상세 동기화.

        KT 리스트 API가 isContainsContents=1이면 본문까지 함께 주므로,
        공고마다 상세 페이지를 다시 긁지 않고 한 번의 요청으로 끝낸다.
        """
        target_pairs = self.service.get_jobs_without_details(
            source=KT, job_ids=job_ids, limit=limit
        )
        if not target_pairs:
            return "처리할 공고가 없습니다."

        raw_jobs = KTClient().fetch_jobs(include_contents=True)
        contents_by_id = {
            extract_kt_platform_id(raw): raw.get("contents") or ""
            for raw in raw_jobs
        }

        fetched: list[JobDetail] = []
        for internal_id, platform_id in target_pairs:
            html = contents_by_id.get(int(platform_id))
            if not html:
                continue
            parsed = self._parse_contents_html(html)
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
    def _heading_kind(line: str) -> str | None:
        """제목 줄이면 어떤 섹션인지 반환. 본문 줄이면 None.

        KT 본문은 섹션 제목에 ●, ■ 같은 마커를 붙이고 항목은 '-'로 시작한다.
        마커 없는 줄은 알려진 제목 키워드로 시작할 때만 제목으로 본다.
        """
        stripped = _HEADING_PREFIX.sub("", line).strip()
        if not stripped:
            return None
        if stripped.startswith(_REQUIREMENT_HEADINGS):
            return "requirements"
        if stripped.startswith(_PREFERRED_HEADINGS):
            return "preferred_points"
        # 다른 섹션 제목이면 현재 섹션을 닫는다
        if _SECTION_MARKER.match(line) and len(stripped) <= 20:
            return "other"
        return None

    @classmethod
    def _parse_contents_html(cls, html: str) -> dict:
        sections: dict[str, list[str]] = {"requirements": [], "preferred_points": []}
        current: str | None = None

        for line in to_lines(html):
            kind = cls._heading_kind(line)
            if kind in ("requirements", "preferred_points"):
                current = kind
                continue
            if kind == "other" and current is not None:
                current = None
                continue
            if current:
                sections[current].append(line)

        return {
            "requirements": "\n".join(sections["requirements"]) or None,
            "preferred_points": "\n".join(sections["preferred_points"]) or None,
        }
