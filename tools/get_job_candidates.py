import json
from db.connection import get_engine
from services.jobs.job_service import JobService, build_job_url


def get_job_candidates(
    skills: list[str],
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    source: str | None = None,
    years: int | None = None,
    top_n: int = 30,
    include_evaluated: bool = False,
    recent_days: int | None = 30,
    min_score: int = 1,
    only_open: bool = True,
) -> str:
    """미지원 공고 중 skill_tags 매칭 점수 기준 상위 top_n개 후보를 JSON으로 반환.

    Claude Code가 직접 추론할 수 있도록 공고 데이터만 제공.
    employment_type은 한국어("정규직", "인턴", "계약직") 또는 영어("regular", "intern", "contract") 모두 허용.
    source: 플랫폼 필터 ("wanted", "nhn", "remember"). None이면 전체.
    years: 지원자 경력(년수). 설정 시 requirements 텍스트 파싱으로 경력 조건 외 공고 제외.
    recent_days: 최근 N일 내 목록에서 관측된 공고만 (기본 30일. None이면 전체).
        오래 전에만 관측된 공고는 대개 마감된 공고다.
    min_score: 최소 매칭 스킬 개수 (기본 1). 0으로 두면 무매칭 공고도 포함.
    only_open: 소스별 마지막 동기화에 잡힌 공고만 (기본 True). 목록에서 내려간 공고는 마감으로 본다.
        동기화가 오래 밀린 상태에서 넓게 보려면 False.
    location/employment_type 필터는 값이 NULL인 공고도 통과시킨다
        (naver·nhn·kt는 location이, remember·sk·cj는 employment_type이 비어 있음).
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
            source=source,
            recent_days=recent_days,
            only_latest_sync=only_open,
        )
        if not rows:
            if not include_evaluated:
                return "새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."
            return "조건에 맞는 미지원 공고가 없습니다."

        if years is not None:
            rows = service.filter_by_years(rows, years)

        candidates = service.get_recommended_jobs(
            skills=skills, rows=rows, top_k=top_n, min_score=min_score
        )
        if not candidates:
            if min_score > 0:
                return ("매칭된 공고가 없습니다. skill_keywords 등록 후 backfill_skill_tags를 실행했는지 "
                        "확인하거나, min_score=0으로 다시 호출해주세요.")
            return "추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."

        result = [
            {
                "job_id": c.internal_id,
                "url": build_job_url(c.source, c.platform_id),
                "company_name": c.company_name,
                "title": c.title,
                "location": c.location,
                "employment_type": c.employment_type,
                "match_score": c.match_score,
                "matched_skills": c.matched_skills,
                "skill_tags": [{"text": t.text} for t in c.skill_tags],
                "requirements": c.requirements,
                "preferred_points": c.preferred_points,
            }
            for c in candidates
        ]
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
