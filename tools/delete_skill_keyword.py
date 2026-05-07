from db.connection import get_engine
from services.jobs.job_service import JobService


def delete_skill_keyword(keyword: str) -> str:
    """스킬 키워드를 사전에서 삭제합니다."""
    return JobService(get_engine()).delete_keyword(keyword)
