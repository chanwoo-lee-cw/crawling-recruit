from db.connection import get_engine
from services.job_service import JobService


def skip_jobs(job_ids: list[int], reason: str | None = None) -> str:
    """공고를 제외 목록에 추가. 이후 get_unapplied_jobs, get_job_candidates 결과에서 제외됨.

    job_ids: 제외할 공고 ID 목록
    reason: 제외 사유 (선택. 예: "연봉 낮음", "기술스택 불일치")
    """
    try:
        engine = get_engine()
        service = JobService(engine)
        return service.skip_jobs(job_ids, reason)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
