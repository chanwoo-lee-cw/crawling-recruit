# 채용공고(Job) 기능 요구사항

## 목적
Wanted, Remember 등 외부 플랫폼의 채용공고를 수집·저장하고, 미지원 공고를 조회·추천한다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| JOB-01 | Wanted API에서 채용공고를 페이지 단위로 수집하고 DB에 저장한다 |
| JOB-02 | Remember API에서 채용공고를 페이지 단위로 수집하고 DB에 저장한다 |
| JOB-03 | 동일 공고(source + platform_id)가 재수집될 경우 upsert 처리한다 |
| JOB-04 | 더 이상 목록에 없는 공고는 `is_active = False`로 마킹한다 (full_sync 시) |
| JOB-05 | 저장된 프리셋(preset_name)을 지정하면 해당 파라미터로 동기화한다 |
| JOB-06 | 이미 지원한 공고(applications 테이블 기준)를 제외하고 미지원 공고 목록을 반환한다 |
| JOB-07 | 위치(location), 고용형태(employment_type), 직군(job_group_id) 필터를 지원한다 |
| JOB-08 | skip된 공고는 미지원 공고 목록에서 제외한다 |

## 비기능 요구사항

- 크롤링 딜레이: 요청 간 `CRAWL_DELAY_SECONDS` 준수 (현재 1초)
- 기본 수집 페이지: `DEFAULT_LIMIT_PAGES` (현재 20페이지)
- 쿠키/API 키는 `.env`에서 관리하며 코드에 포함하지 않는다

## 범위 밖 (Out of Scope)

- 채용공고 직접 지원 (외부 플랫폼에서 수행)
- 공고 상세 정보(requirements, skill_tags) 수집 → job-details 도메인 담당

## 수용 기준 (Acceptance Criteria)

- `sync_jobs()` 호출 시 신규/변경/비활성화 개수가 포함된 결과 문자열 반환
- 동일 source+platform_id 공고를 두 번 수집해도 중복 없이 최신 상태 유지
- `is_active=False` 공고는 미지원 공고 목록에서 자동 제외
