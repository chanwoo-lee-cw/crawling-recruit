from db.connection import get_engine
from services.job_service import JobService


def save_job_evaluations(evaluations: list[dict]) -> str:
    """Claude가 평가한 공고 verdict를 저장한다.

    evaluations: [{"job_id": int, "verdict": "good"|"pass"|"skip"}, ...]
    - good: 지원 고려 대상
    - pass: 이번엔 해당 없음 (다음 세션에서 다시 나오지 않음)
    - skip: 영구 제외
    get_job_candidates는 이미 평가된 공고를 기본 제외하므로,
    받은 모든 공고에 verdict를 저장해야 다음 세션에서 재처리되지 않는다.
    """
    try:
        engine = get_engine()
        service = JobService(engine)
        return service.save_job_evaluations(evaluations)
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
