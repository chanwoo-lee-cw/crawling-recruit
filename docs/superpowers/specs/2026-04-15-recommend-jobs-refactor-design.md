# recommend_jobs MCP 리팩터링 설계

**날짜:** 2026-04-15  
**상태:** 승인됨

## 배경

기존 `recommend_jobs` MCP 툴은 툴 내부에서 Anthropic API를 직접 호출해 Claude가 추천을 수행했다. 이는 MCP 아키텍처 원칙에 어긋난다. MCP 서버는 데이터와 도구를 제공하고, 추론은 MCP 클라이언트(Claude Code)가 직접 수행해야 한다.

## 변경 사항

### 제거

- `tools/recommend_jobs.py` 삭제
- `main.py`에서 `recommend_jobs` 등록 제거

### 추가: `get_job_candidates` 툴

**파일:** `tools/get_job_candidates.py`

```python
def get_job_candidates(
    skills: list[str],
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    top_n: int = 30,
) -> str:
```

**동작:**

1. `JobService.get_unapplied_job_rows()`로 필터 조건(job_group_id, location, employment_type)에 맞는 미지원 공고 전체 조회
2. `JobService.get_recommended_jobs(skills, rows, top_k=top_n)`으로 skill_tags 매칭 점수 기준 상위 `top_n`개 선별
3. 각 공고의 `job_id`, `company_name`, `title`, `location`, `employment_type`, `skill_tags`, `requirements`, `preferred_points` 포함한 JSON 문자열 반환

**반환 예시:**

```json
[
  {
    "job_id": 12345,
    "company_name": "토스플레이스",
    "title": "Backend Developer",
    "location": "서울 서초구",
    "employment_type": "regular",
    "skill_tags": [{"text": "Kotlin"}, {"text": "Java"}],
    "requirements": "...",
    "preferred_points": "..."
  }
]
```

## 데이터 흐름

```
Claude Code
  → get_job_candidates(skills, filters)   # MCP 툴: 필터링 + skill 매칭
  ← JSON 후보 목록
  → Claude가 직접 추천 + 이유 설명       # 추론은 Claude Code가 담당
```

## 재사용

`job_service.py`는 변경 없음. 기존 `get_unapplied_job_rows`, `get_recommended_jobs` 메서드를 그대로 재사용.

## 기대 효과

- Anthropic API 이중 호출 제거 → 별도 API 키 불필요
- Claude Code가 requirements 전문까지 직접 읽고 추론 → 추천 품질 향상
- MCP 서버 역할이 명확해짐 (데이터 제공만)
