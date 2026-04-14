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

**파라미터 계약:**

- `employment_type`: 한국어(`"정규직"`, `"인턴"`, `"계약직"`) 또는 영어(`"regular"`, `"intern"`, `"contract"`) 모두 허용. `JobService.EMPLOYMENT_TYPE_MAP`이 내부에서 변환 처리.
- `top_n`: 기본값 30. `get_recommended_jobs`의 기본값(15)보다 크게 설정해 Claude Code가 더 넓은 후보군에서 추론할 수 있도록 함.

**동작:**

1. `JobService.get_unapplied_job_rows()`로 필터 조건(job_group_id, location, employment_type)에 맞는 미지원 공고 전체 조회
2. `JobService.get_recommended_jobs(skills, rows, top_k=top_n)`으로 skill_tags 매칭 점수 기준 상위 `top_n`개 선별 (이 메서드는 `fetched_at is None`인 공고를 자동 제외)
3. 빈 결과 케이스별 반환 문자열:
   - 1단계에서 rows가 0개: `"조건에 맞는 미지원 공고가 없습니다."`
   - 2단계 후 후보가 0개 (모든 rows의 `fetched_at`이 NULL — job_details 미수집): `"추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."`
   - 참고: `get_recommended_jobs`는 skill 점수가 0이어도 `fetched_at`이 있는 공고는 모두 반환(점수순 정렬)하므로, "skill 미매칭으로 인한 0개" 케이스는 발생하지 않음
4. 후보가 있으면 각 공고를 JSON 직렬화하여 반환. 키 매핑: jobs 테이블의 `id` → JSON의 `"job_id"`. `skill_tags`는 DB 저장값 그대로 전달(Wanted API 원본 형태 유지).
5. 예외 발생 시 한국어 에러 문자열 반환 (다른 툴과 동일한 에러 처리 패턴).

**반환 예시 (정상):**

```json
[
  {
    "job_id": 12345,
    "company_name": "토스플레이스",
    "title": "Backend Developer",
    "location": "서울 서초구",
    "employment_type": "regular",
    "skill_tags": [{"id": 97, "text": "Kotlin", "kind_name": "language"}, ...],
    "requirements": "...",
    "preferred_points": "..."
  }
]
```

**반환 예시 (상세 정보 없음):**

```
"추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."
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
