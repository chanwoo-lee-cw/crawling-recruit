from db.connection import get_engine
from services.jobs.job_service import JobService


def backfill_skill_tags(days: int | None = 30, source: str | None = None) -> str:
    """등록된 스킬 키워드로 이미 수집된 공고 상세를 재스캔해 skill_tags를 채운다.

    재크롤 없이 DB에 저장된 requirements/preferred_points 텍스트만 사용한다.
    days: 최근 N일 내 목록에서 관측된 공고만 대상 (None이면 전체).
    source: 특정 플랫폼만 처리 ("wanted", "naver" 등). None이면 전체.
    get_job_candidates의 매칭 점수는 skill_tags에 의존하므로, 키워드 추가 후 실행할 것.
    """
    try:
        return JobService(get_engine()).backfill_skill_tags(days=days, source=source)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
