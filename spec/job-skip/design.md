# 공고 제외(Job Skip) 설계

## 스키마

```
job_skips
├── job_id      INT PK FK→jobs.internal_id ON DELETE CASCADE
├── reason      VARCHAR(255) NULL
└── skipped_at  DATETIME NOT NULL
```

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `skip_jobs` | 공고 제외 목록 추가 | `job_ids: list[int]`, `reason: str \| None` |

## 필터링 적용 위치

`get_unapplied_job_rows` 쿼리의 LEFT JOIN + IS NULL 패턴:

```sql
LEFT JOIN job_skips ON jobs.internal_id = job_skips.job_id
WHERE job_skips.job_id IS NULL
```

같은 패턴을 `job_evaluations` 필터도 사용한다.

## 에러 처리

| 상황 | 처리 |
|------|------|
| job_ids 빈 리스트 | `"제외할 공고 ID를 입력해주세요."` 반환 |
| 존재하지 않는 job_id | FK 제약 위반 → 예외 캐치 후 에러 문자열 반환 |
