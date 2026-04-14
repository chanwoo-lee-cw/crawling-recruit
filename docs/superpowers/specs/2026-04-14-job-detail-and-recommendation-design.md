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

```sql
job_details (
    job_id           INT PRIMARY KEY,  -- jobs.id 참조
    requirements     TEXT,             -- 자격요건 (자연어)
    preferred_points TEXT,             -- 우대사항 (자연어)
    skill_tags       JSON,             -- [{"tag_type_id": 1554, "text": "Python"}, ...]
    fetched_at       DATETIME
)
```

## MCP 툴 구성

### 기존 툴 (변경 없음)

- `sync_jobs`: 공고 목록 동기화
- `sync_applications`: 지원 현황 동기화
- `get_unapplied_jobs`: 미지원 공고 조회
- `save_search_preset` / `list_search_presets`: 프리셋 관리
- `debug_applications`: 디버그용

### 신규 툴

#### `sync_job_details`

```python
sync_job_details(
    job_ids: list[int] | None = None,  # None이면 detail 없는 공고 전체
    limit: int | None = None           # 배치 크기 제한
) -> str
```

- `job_ids` 미지정 시 `job_details`가 없는 공고 전체 대상
- `limit`으로 한 번에 처리할 최대 공고 수 조절
- 직접 호출 및 배치 실행 모두 지원

#### `recommend_jobs`

```python
recommend_jobs(
    skills: list[str],                   # ["Python", "FastAPI", "React"]
    location: str | None = None,
    employment_type: str | None = None,
    top_n: int = 10
) -> str
```

- 미지원 공고 중 detail 없는 건 lazy fetch 후 진행 (최대 20개 한도)
- skill_tags 기준 SQL 1차 필터로 상위 15개 선별
- Claude API로 requirements + preferred_points 기반 최종 top_n 추천

## 데이터 흐름

### sync_job_details

```
jobs 테이블에서 job_details 없는 job_id 추출
  → limit 적용
  → Wanted detail API 순차 호출 (1초 딜레이)
  → job_details upsert
  → "완료: N개 신규, M개 업데이트" 반환
```

### recommend_jobs

```
get_unapplied_jobs (location / employment_type 필터)
  → detail 없는 공고 lazy fetch (최대 20개)
  → skill_tags JSON에서 skills 파라미터와 교집합 계산
  → 매칭 수 기준 상위 15개 선별
  → Claude API 호출:
      - 입력: requirements + preferred_points + skills
      - 출력: top_n 추천 목록 + 공고별 한 줄 이유
  → 결과 반환
```

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| detail API 호출 실패 | 해당 공고 스킵, 나머지로 진행 |
| skill_tags 비어있는 공고 | SQL 필터 통과시켜 LLM 판단에 위임 |
| Claude API 호출 실패 | skill_tags 매칭 결과만 반환 |
| 미지원 공고 없음 | 즉시 "미지원 공고 없음" 반환 |

## 파일 구조 변경

```
db/
  models.py          # job_details 테이블 추가
services/
  wanted_client.py   # fetch_job_detail() 메서드 추가
  job_service.py     # upsert_job_details(), get_recommended_jobs() 추가
tools/
  sync_job_details.py   # 신규
  recommend_jobs.py     # 신규
main.py              # 두 툴 등록
```

## 외부 의존성

- Claude API (`anthropic` SDK): recommend_jobs의 2차 추천에 사용
- 기존 의존성(httpx, sqlalchemy, fastmcp) 외 `anthropic` 패키지 추가
