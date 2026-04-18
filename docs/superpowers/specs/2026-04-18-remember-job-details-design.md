# Remember 공고 상세 저장 설계

## 배경

`sync_jobs`로 수집한 Remember 공고는 `job_details` 테이블이 비어 있어 `get_job_candidates`에서 제외된다. Remember listing API 응답에는 이미 상세 필드가 포함되어 있으므로 별도 API 호출 없이 `sync_jobs` 시점에 함께 저장한다.

## 목표

- Remember `sync_jobs` 실행 시 `job_details`도 함께 upsert
- `sync_job_details`를 별도 실행하지 않아도 `get_job_candidates`가 Remember 공고를 반환

## 변경 범위

### 1. `_parse_remember_job` 확장 (`services/job_service.py`)

listing 응답에서 상세 필드 추출:

| Remember 응답 필드         | job_details 컬럼   |
|--------------------------|------------------|
| `qualifications`         | `requirements`   |
| `preferred_qualifications` | `preferred_points` |
| `job_categories[*].level2` (목록) | `skill_tags` (JSON 배열) |

반환 딕셔너리에 `_detail` 키로 상세 정보를 포함시켜 `upsert_jobs`에 전달한다.

### 2. `upsert_jobs` Remember 분기 추가 (`services/job_service.py`)

`source == "remember"`일 때, job upsert 완료 후 각 공고의 `internal_id`를 조회하여 `job_details` upsert 수행. `fetched_at`은 `synced_at`과 동일 값 사용.

### 3. 변경 없는 부분

- `get_jobs_without_details`: `source == "wanted"` 필터 유지 (Remember는 이미 채워짐)
- `sync_job_details` 툴: Wanted 전용으로 유지
- `get_job_candidates`: 변경 없음, Remember 공고도 자동으로 후보에 포함됨

## 데이터 흐름

```
sync_jobs(source="remember")
  └─ RememberClient.fetch_jobs()
       └─ listing API 응답 (qualifications, preferred_qualifications, job_categories 포함)
            └─ _parse_remember_job() → job row + detail dict
                 └─ upsert_jobs()
                      ├─ jobs 테이블 upsert
                      └─ job_details 테이블 upsert (fetched_at = synced_at)
```

## 구현 시 주의사항

- `_parse_remember_job`이 반환하는 딕셔너리에 `_detail` 같은 임시 키를 추가하면 `insert(Job.__table__).values(rows)` 시 컬럼 오류 발생 → detail 데이터는 별도 리스트로 분리해서 전달
- `skill_tags`는 `job_categories` 리스트에서 `level2` 값만 추출한 문자열 배열로 저장
