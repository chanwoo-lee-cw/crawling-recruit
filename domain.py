import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SkillTag:
    text: str


@dataclass
class JobCandidate:
    """DB 읽기 경로 전용: get_unapplied_job_rows → get_recommended_jobs → get_job_candidates"""
    id: int
    company_name: str
    title: str
    location: str | None
    employment_type: str | None
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[SkillTag]   # text만 보존 — 매칭 전용
    fetched_at: datetime | None

    @classmethod
    def from_row(cls, row) -> "JobCandidate":
        """DB row(dict/Mapping) → JobCandidate. skill_tags JSON 파싱 포함.
        id, company_name, title은 DB NOT NULL 컬럼이므로 직접 접근."""
        raw_tags = row.get("skill_tags") or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except (json.JSONDecodeError, TypeError):
                raw_tags = []
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row.get("location"),
            employment_type=row.get("employment_type"),
            requirements=row.get("requirements"),
            preferred_points=row.get("preferred_points"),
            skill_tags=[SkillTag(text=t["text"]) for t in raw_tags if t.get("text")],
            fetched_at=row.get("fetched_at"),
        )


@dataclass
class JobDetail:
    """쓰기 경로 전용: fetch_job_detail → upsert_job_details.
    skill_tags는 raw API dict 보존 — DB JSON 컬럼에 그대로 저장."""
    job_id: int
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[dict]
