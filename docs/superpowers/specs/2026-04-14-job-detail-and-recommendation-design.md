# Job Detail 수집 및 기술스택 기반 추천 기능 설계

## 개요

원티드 채용공고의 상세 정보(requirements, skill_tags 등)를 별도로 수집하고,
사용자의 기술스택 파라미터를 기반으로 미지원 공고를 추천하는 기능을 추가한다.

## 결정 사항

- 기술스택은 DB에 저장하지 않고 호출 시 파라미터로 전달
- 추천 방식: skill_tags SQL 1차 필터 → Claude API 2차 정밀 추천 (하이브리드)
- sync_jobs와 sync_job_details는 독립 툴로 분리, 각각 직접 호출 및 배치 실행 가능
- detail이 없는 공고는 recommend_jobs 호출 시 lazy fetch

## DB 스키마

### 기존 테이블 (변경 없음)

- `jobs`: 공고 기본 정보
- `applications`: 지원 현황
- `search_presets`: 검색 프리셋

### 신규 테이블

```python
job_details_table = Table(
    "job_details", metadata,
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("requirements", Text),
    Column("preferred_points", Text),
    Column("skill_tags", JSON),   # [{"tag_type_id": 1554, "text": "Python"}, ...]
    Column("fetched_at", DateTime, nullable=False),
)
```

- `job_id`는 `jobs.id`의 FK, `ON DELETE CASCADE`
- `skill_tags`는 Wanted detail API 응답의 `data.skill_tags` 배열 그대로 저장

## Wanted Detail API

### Endpoint

```
GET https://www.wanted.co.kr/api/chaos/jobs/v4/{job_id}/details
```

인증 불필요 (공개 API). 쿠키 없이 호출 가능.

### 응답 필드 매핑

| DB 컬럼 | API 응답 경로 |
|---|---|
| `requirements` | `data.job.detail.requirements` |
| `preferred_points` | `data.job.detail.preferred_points` |
| `skill_tags` | `data.skill_tags` |

### WantedClient 추가 메서드

```python
def fetch_job_detail(self, job_id: int) -> dict | None:
    """단일 공고 detail 조회. 실패 시 None 반환."""
```

- `_get()` 메서드 재사용 (기존 retry/rate-limit 로직 포함)
- 호출 간 1초 딜레이는 호출자(`sync_job_details`)가 책임

## MCP 툴 구성

### 기존 툴 (변경 없음)

- `sync_jobs`, `sync_applications`, `get_unapplied_jobs`
- `save_search_preset`, `list_search_presets`, `debug_applications`

### 신규 툴

#### `sync_job_details`

```python
sync_job_details(
    job_ids: list[int] | None = None,  # None이면 job_details 없는 공고 전체
    limit: int | None = None           # 한 번에 처리할 최대 공고 수
) -> str
```

- `job_ids` 미지정 시 `job_details`가 없는 공고 전체 대상
- `job_ids`와 `limit` 동시 지정 시: `job_ids` 목록을 우선 사용하되 `limit`개까지만 처리
- 공고 간 1초 딜레이
- upsert 방식: 항상 덮어쓰기 (content diff 없음), `fetched_at`은 `upsert_job_details()`가 `datetime.now()`로 설정
- 반환: `"완료: N개 처리"` (신규/갱신 구분 없음)

#### `recommend_jobs`

```python
recommend_jobs(
    skills: list[str],                   # ["Python", "FastAPI", "React"]
    location: str | None = None,
    employment_type: str | None = None,
    job_group_id: int | None = None,
    top_n: int = 10
) -> str
```

## 데이터 흐름

### sync_job_details

```
jobs 테이블에서 job_details 없는 job_id 추출 (limit 적용)
  → Wanted detail API 순차 호출 (공고 간 1초 딜레이)
  → 실패 시 해당 공고 스킵, 경고 포함해 계속 진행
  → job_details upsert (항상 덮어쓰기)
  → "완료: N개 처리" 반환
```

### recommend_jobs

```
JobService.get_unapplied_job_rows() 호출 (str 아닌 list[dict] 반환하는 내부 메서드)
  - location, employment_type, job_group_id 필터 적용
  - 상한 없이 전체 미지원 공고 대상

  → 위 필터 결과 중 job_details 없는 공고 최대 20개 lazy fetch (필터 외 공고는 fetch 안 함)

  → 필터된 미지원 공고 (detail 있는 것) 대상으로 skill_tags 매칭 점수 계산
      점수 = skills 파라미터와 skill_tags.text 교집합 수
      (skill_tags 비어있는 공고는 점수 0으로 포함, LLM 판단에 위임)

  → 점수 기준 상위 15개 선별

  → Claude API 호출 (claude-sonnet-4-6):
      system: "당신은 채용 어시스턴트입니다."
      user: skills 목록 + 상위 15개 공고 목록
            (공고당 포함 필드: job_id, company_name, title, requirements, preferred_points)
      → top_n 추천 결과 + 공고별 한 줄 이유 반환 (응답에 job_id 포함 요구)
      → 응답에서 job_id로 DB rows와 매핑하여 링크 포함 Markdown 테이블 구성
      → 후보 목록에 없는 job_id는 무시 (hallucination 방어)

  → 결과 Markdown 테이블로 반환
```

**내부 메서드 분리:**
- `JobService.get_unapplied_job_rows()`: `jobs LEFT JOIN job_details` 쿼리, `LIMIT` 절 없음 (전체 조회)
  반환 필드: `id, company_name, title, location, employment_type, requirements, preferred_points, skill_tags`
  (`job_details` 없는 공고는 detail 필드가 `None`으로 포함)
- 기존 `get_unapplied_jobs()`는 변경 없이 문자열 반환 유지

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| detail API 호출 실패 | 해당 공고 스킵, 나머지로 진행 |
| skill_tags 비어있는 공고 | 점수 0으로 후보 포함, LLM 판단에 위임 |
| Claude API 호출 실패 | skill_tags 매칭 점수 순 결과만 반환 |
| 미지원 공고 없음 | 즉시 "미지원 공고 없음" 반환 |
| lazy fetch 후에도 detail 없음 | detail 있는 공고만으로 진행 |

## 환경변수

`.env.example`에 추가:

```
ANTHROPIC_API_KEY=your_api_key_here
```

## 파일 구조 변경

```
db/
  models.py              # job_details_table 추가
services/
  wanted_client.py       # fetch_job_detail() 메서드 추가
  job_service.py         # upsert_job_details(), get_unapplied_job_rows(),
                         # get_recommended_jobs() 추가
tools/
  sync_job_details.py    # 신규
  recommend_jobs.py      # 신규
main.py                  # 두 툴 등록
.env.example             # ANTHROPIC_API_KEY 추가
requirements.txt         # anthropic 패키지 추가
```

## 외부 의존성 추가

- `anthropic>=0.30.0`: Claude API SDK (`recommend_jobs`의 2차 추천)
- 모델: `claude-sonnet-4-6`
- API 키: `ANTHROPIC_API_KEY` 환경변수

## fetch_job_detail 반환 구조

`fetch_job_detail`은 파싱된 dict를 반환한다 (raw API 응답 아님):

```python
{
    "job_id": int,
    "requirements": str | None,
    "preferred_points": str | None,
    "skill_tags": list[dict],  # [{"tag_type_id": int, "text": str}, ...]
}
```

실패 시 `None` 반환. `upsert_job_details()`는 이 구조를 그대로 받아 저장한다.
