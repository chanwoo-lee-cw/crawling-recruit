# 공고 제외(Job Skip) 기능 요구사항

## 목적
관심 없는 공고를 수동으로 제외 목록에 추가하여, 이후 조회에서 영구적으로 숨긴다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| SK-01 | 하나 이상의 job_id를 제외 목록에 추가한다 |
| SK-02 | 선택적으로 제외 사유(reason)를 기록한다 |
| SK-03 | 이미 제외된 공고를 다시 skip해도 upsert로 처리된다 (중복 오류 없음) |
| SK-04 | skip된 공고는 `get_unapplied_jobs`, `get_job_candidates` 결과에서 제외된다 |

## 비기능 요구사항

- job_id는 `jobs.internal_id` 기준이다 (platform_id 아님)
- 제외된 공고를 되돌리는 기능은 제공하지 않는다 (DB 직접 삭제로 대응)

## 범위 밖 (Out of Scope)

- 제외 취소(undo)
- 제외 목록 조회 툴

## 수용 기준 (Acceptance Criteria)

- `skip_jobs([101, 102], reason="연봉 낮음")` 호출 시 `"2개 공고 제외 완료 (사유: 연봉 낮음)"` 반환
- skip 후 해당 공고가 `get_unapplied_jobs` 결과에서 사라짐
