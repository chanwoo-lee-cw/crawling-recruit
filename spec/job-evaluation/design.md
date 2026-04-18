# 공고 평가 캐시(Job Evaluation) 설계

## 스키마

```
job_evaluations
├── job_id        INT PK FK→jobs.internal_id ON DELETE CASCADE
├── verdict       VARCHAR(20) NOT NULL  -- "good" | "pass" | "skip"
└── evaluated_at  DATETIME NOT NULL
```

verdict 의미:

| verdict | 의미 |
|---------|------|
| `good` | 지원 고려 대상으로 추천한 공고 |
| `pass` | 읽었지만 현재 조건에 맞지 않는 공고 |
| `skip` | 영구 제외 예약 (현재는 get_job_candidates에서만 제외) |

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `get_job_candidates` | skill 매칭 후보 JSON 반환 | `skills`, `include_evaluated` |
| `save_job_evaluations` | Claude의 verdict 저장 | `evaluations: [{"job_id": int, "verdict": str}, ...]` |

## Claude 워크플로우

```
1. get_job_candidates(skills=[...])
   → job_evaluations에 없는 공고만 반환 (job_id 포함)

2. Claude가 공고 읽고 2차 추론 → 추천 목록 사용자에게 제시

3. Claude가 save_job_evaluations 자동 호출
   → 받은 모든 공고 verdict 저장
     추천한 것: "good" / 그 외: "pass"

4. 다음 세션: 평가된 공고 제외 → 새 공고만 읽음
```

## 필터링 적용 위치

`get_unapplied_job_rows`의 LEFT JOIN + IS NULL 패턴 (job_skips와 동일):

```sql
LEFT JOIN job_evaluations ON jobs.internal_id = job_evaluations.job_id
-- include_evaluated=False일 때만:
WHERE job_evaluations.job_id IS NULL
```

## 에러 처리

| 상황 | 처리 |
|------|------|
| 허용 외 verdict | `ValueError("유효하지 않은 verdict: ...")` → 에러 문자열 반환 |
| 빈 리스트 | `"0개 처리"` 반환 |
| 미평가 공고 0개 | `"새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."` |
