import json
import os
import time
import anthropic
from db.connection import get_engine
from services.wanted_client import WantedClient
from services.job_service import JobService

CLAUDE_MODEL = "claude-sonnet-4-6"
LAZY_FETCH_LIMIT = 20


def recommend_jobs(
    skills: list[str],
    location: str | None = None,
    employment_type: str | None = None,
    job_group_id: int | None = None,
    top_n: int = 10,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    # 1. 미지원 공고 전체 조회 (필터 적용, LIMIT 없음)
    all_rows = service.get_unapplied_job_rows(
        job_group_id=job_group_id,
        location=location,
        employment_type=employment_type,
    )
    if not all_rows:
        return "미지원 공고가 없습니다."

    # 2. detail 없는 공고 lazy fetch (최대 LAZY_FETCH_LIMIT개)
    missing = [r for r in all_rows if r.get("fetched_at") is None][:LAZY_FETCH_LIMIT]
    if missing:
        fetched = []
        for i, row in enumerate(missing):
            if i > 0:
                time.sleep(1)
            detail = client.fetch_job_detail(row["id"])
            if detail:
                fetched.append(detail)
        if fetched:
            service.upsert_job_details(fetched)
        # detail 업데이트 후 한 번만 재조회
        all_rows = service.get_unapplied_job_rows(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
        )

    # 3. 이미 조회된 all_rows를 직접 전달 (DB 재조회 없음)
    candidates = service.get_recommended_jobs(
        skills=skills,
        rows=all_rows,
        top_k=15,
    )
    if not candidates:
        return "추천할 공고가 없습니다. (상세 정보 없음)"

    # 4. Claude API로 최종 추천
    candidate_ids = {c["id"] for c in candidates}
    try:
        prompt_jobs = "\n\n".join(
            f"job_id: {c['id']}\n회사: {c['company_name']}\n포지션: {c['title']}\n"
            f"자격요건: {c.get('requirements') or '정보 없음'}\n"
            f"우대사항: {c.get('preferred_points') or '정보 없음'}"
            for c in candidates
        )
        user_message = (
            f"내 기술스택: {', '.join(skills)}\n\n"
            f"다음 채용공고 중 내 스택과 가장 잘 맞는 상위 {top_n}개를 추천해줘.\n"
            f"반드시 JSON 배열로만 응답해: "
            f'[{{"job_id": <int>, "reason": "<한 줄 이유>"}}]\n\n'
            f"{prompt_jobs}"
        )
        ai_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = ai_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system="당신은 채용 어시스턴트입니다. 요청한 JSON 형식으로만 응답하세요.",
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # JSON 파싱 및 hallucination 방어
        recommendations = json.loads(raw)
        recommendations = [r for r in recommendations if r.get("job_id") in candidate_ids]
        recommendations = recommendations[:top_n]

        job_map = {c["id"]: c for c in candidates}
        lines = [f"## 추천 공고 Top {len(recommendations)}\n",
                 "| 회사명 | 포지션 | 지역 | 추천 이유 | 링크 |",
                 "|---|---|---|---|---|"]
        for rec in recommendations:
            job = job_map[rec["job_id"]]
            link = f"https://www.wanted.co.kr/wd/{job['id']}"
            lines.append(
                f"| {job['company_name']} | {job['title']} | {job['location']} "
                f"| {rec['reason']} | {link} |"
            )
        return "\n".join(lines)

    except Exception:
        # Claude 실패 시 skill_tags 점수 순 결과 반환
        lines = ["## 추천 공고 (skill_tags 매칭 기준)\n",
                 "| 회사명 | 포지션 | 지역 | 링크 |",
                 "|---|---|---|---|"]
        for c in candidates[:top_n]:
            link = f"https://www.wanted.co.kr/wd/{c['id']}"
            lines.append(f"| {c['company_name']} | {c['title']} | {c['location']} | {link} |")
        return "\n".join(lines)
