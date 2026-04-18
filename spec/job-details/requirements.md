# 공고 상세(Job Detail) 기능 요구사항

## 목적
채용공고의 상세 정보(자격요건, 우대사항, 스킬태그)를 수집하여 Claude의 2차 추천에 필요한 데이터를 제공한다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| JD-01 | `job_details` 레코드가 없는 공고(상세 미수집)를 대상으로 상세 정보를 수집한다 |
| JD-02 | Wanted 공고 상세 페이지에서 requirements, preferred_points, skill_tags를 크롤링한다 |
| JD-03 | 크롤링 실패(None 반환) 시 해당 공고를 건너뛰고 계속 진행한다 |
| JD-04 | 수집 요청 간 `CRAWL_DELAY_SECONDS` 딜레이를 적용한다 |
| JD-05 | `get_job_candidates`는 `fetched_at IS NULL`인 공고(상세 미수집)를 자동 제외한다 |

## 비기능 요구사항

- 상세 수집 실패율이 높을 경우 별도 재시도 없이 다음 공고로 넘어간다
- 크롤링 딜레이로 인해 다수 공고 처리 시 시간이 소요될 수 있음을 감안한다

## 범위 밖 (Out of Scope)

- Remember 공고 상세 수집 (API 제공 없음, 목록에서 requirements 포함)
- 이미 수집된 상세 정보 갱신 (재수집 필요 시 수동 삭제 후 재실행)

## 수용 기준 (Acceptance Criteria)

- `sync_job_details()` 호출 시 처리 건수 포함 결과 문자열 반환
- 크롤링 실패한 공고는 건너뛰고 성공한 공고만 저장
- 상세 수집 후 `get_job_candidates`에서 해당 공고가 후보에 포함
