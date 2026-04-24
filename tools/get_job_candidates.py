import json
from db.connection import get_engine
from services.jobs.job_service import JobService, JOB_BASE_URLS, WANTED_JOB_BASE_URL


def get_job_candidates(
    skills: list[str],
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    top_n: int = 30,
    include_evaluated: bool = False,
) -> str:
    """미지원 공고 중 skill_tags 매칭 점수 기준 상위 top_n개 후보를 JSON으로 반환.

    Claude Code가 직접 추론할 수 있도록 공고 데이터만 제공.
    employment_type은 한국어("정규직", "인턴", "계약직") 또는 영어("regular", "intern", "contract") 모두 허용.
    추천 후 save_job_evaluations를 호출해 각 공고 verdict를 저장할 것. job_id 필드 사용.
    """
    try:
        engine = get_engine()
        service = JobService(engine)

        rows = service.get_unapplied_job_rows(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            include_evaluated=include_evaluated,
        )
        if not rows:
            if not include_evaluated:
                return "새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."
            return "조건에 맞는 미지원 공고가 없습니다."

        candidates = service.get_recommended_jobs(skills=skills, rows=rows, top_k=top_n)
        if not candidates:
            return "추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."

        result = [
            {
                "job_id": c.internal_id,
                "url": f"{JOB_BASE_URLS.get(c.source, WANTED_JOB_BASE_URL)}/{c.platform_id}",
                "company_name": c.company_name,
                "title": c.title,
                "location": c.location,
                "employment_type": c.employment_type,
                "skill_tags": [{"text": t.text} for t in c.skill_tags],
                "requirements": c.requirements,
                "preferred_points": c.preferred_points,
            }
            for c in candidates
        ]
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
