from db.connection import get_engine
from services.jobs.job_service import JobService


def list_skill_keywords() -> str:
    """등록된 스킬 키워드 목록을 반환합니다."""
    keywords = JobService(get_engine()).list_keywords()
    if not keywords:
        return "등록된 키워드가 없습니다."
    lines = ["| 키워드 |", "|---|"]
    lines.extend(f"| {kw} |" for kw in keywords)
    lines.append(f"총 {len(keywords)}개")
    return "\n".join(lines)
