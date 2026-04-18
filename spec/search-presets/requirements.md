# 검색 프리셋(Search Preset) 기능 요구사항

## 목적
자주 사용하는 동기화 파라미터를 이름으로 저장하고, `sync_jobs` 호출 시 preset_name으로 재사용한다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| SP-01 | 이름과 파라미터 딕셔너리를 저장한다 |
| SP-02 | 동일 이름의 프리셋이 이미 존재하면 덮어쓴다 (upsert) |
| SP-03 | 허용된 키(`ALLOWED_PRESET_KEYS`) 외의 키가 포함되면 에러를 반환한다 |
| SP-04 | 저장된 프리셋 목록을 조회할 수 있다 |
| SP-05 | `sync_jobs(preset_name=...)` 호출 시 해당 프리셋의 파라미터로 동기화한다 |

## 비기능 요구사항

- 허용 키: `job_group_id`, `job_ids`, `years`, `locations`, `limit_pages`, `job_category_names`, `min_experience`, `max_experience`, `source`

## 범위 밖 (Out of Scope)

- 프리셋 삭제
- 프리셋 이름 변경 (재저장으로 대체)

## 수용 기준 (Acceptance Criteria)

- 허용 키만 포함된 프리셋 저장 성공
- 허용 키 외 포함 시 `"유효하지 않은 파라미터 키"` 포함 에러 반환
- `sync_jobs(preset_name="백엔드 신입")` 호출 시 해당 파라미터로 동기화
