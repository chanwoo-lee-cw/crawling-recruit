from db.connection import get_engine
from services.jobs.job_service import JobService


def add_skill_keyword(keyword: str) -> str:
    """스킬 키워드를 사전에 추가합니다."""
    return JobService(get_engine()).add_keyword(keyword)
