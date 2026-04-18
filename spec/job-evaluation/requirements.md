# 공고 평가 캐시(Job Evaluation) 기능 요구사항

## 목적
Claude가 2차 추천 후 각 공고에 대한 verdict를 저장하여, 다음 세션에서 이미 평가한 공고를 다시 읽지 않도록 한다. 토큰 낭비를 방지한다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| EV-01 | Claude가 추천 후 각 공고의 verdict(`good`/`pass`/`skip`)를 저장한다 |
| EV-02 | `get_job_candidates`는 기본적으로 이미 평가된 공고를 제외한다 (`include_evaluated=False`) |
| EV-03 | `include_evaluated=True`로 호출하면 평가 여부에 무관하게 전체 후보를 반환한다 |
| EV-04 | 미평가 공고가 0개이면 `include_evaluated=True` 힌트를 포함한 메시지를 반환한다 |
| EV-05 | 동일 공고를 재평가할 수 있다 (upsert — 덮어쓰기) |
| EV-06 | `sync_jobs`로 새로운 공고가 유입되면 평가 없으므로 다음 추천에 자동 포함된다 |
| EV-07 | `get_job_candidates` 반환 JSON에 `job_id`가 포함되어 Claude가 `save_job_evaluations` 호출 시 사용한다 |

## 비기능 요구사항

- Claude는 `get_job_candidates` 후 받은 **모든** 공고에 verdict를 저장해야 한다 (일부만 저장하면 저장 안 된 공고가 다음 세션에서 재등장)
- `evaluated_at`은 서버 측 UTC 시각으로 기록한다

## 범위 밖 (Out of Scope)

- 사용자 직접 평가 UI
- verdict별 공고 통계 조회
- `skip` verdict 공고를 `job_skips`와 연동하는 기능 (현재 예약만)

## 수용 기준 (Acceptance Criteria)

- `save_job_evaluations([{"job_id": 1, "verdict": "good"}])` 호출 시 `"1개 평가 저장 완료"` 반환
- 허용 외 verdict 값 입력 시 에러 문자열 반환
- 평가 저장 후 `get_job_candidates` 재호출 시 해당 공고 제외 확인
- `include_evaluated=True` 호출 시 평가된 공고 포함 반환
