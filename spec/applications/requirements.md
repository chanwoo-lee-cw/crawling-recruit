# 지원현황(Application) 기능 요구사항

## 목적
Wanted, Remember 플랫폼에서 내가 지원한 공고 이력을 수집·저장하여, 미지원 공고 필터링에 활용한다.

## 기능 요구사항

| ID | 요구사항 |
|----|---------|
| APP-01 | Wanted에서 지원 이력(status, apply_time 등)을 수집하고 DB에 저장한다 |
| APP-02 | Remember에서 지원 이력을 수집하고 DB에 저장한다 |
| APP-03 | 동일 지원(source + platform_id) 이력은 upsert 처리한다 |
| APP-04 | 지원 이력이 존재하는 공고는 `get_unapplied_jobs`, `get_job_candidates`에서 자동 제외된다 |
| APP-05 | 지원 이력 제외 판단은 (company_name, title) 쌍 기준으로 한다 — platform_id가 달라도 같은 공고면 제외 |

## 비기능 요구사항

- 쿠키 인증이 필요하며, 만료 시 명확한 안내 메시지를 반환한다
- 지원 이력이 0건이어도 정상 응답(0건 동기화 완료)을 반환한다

## 범위 밖 (Out of Scope)

- 지원 취소/철회 처리
- 지원 결과(합/불) 추적

## 수용 기준 (Acceptance Criteria)

- `sync_applications()` 호출 시 총 동기화 건수 포함 결과 문자열 반환
- 쿠키 만료 시 `"쿠키가 만료되었습니다"` 포함 에러 문자열 반환
- 지원한 공고(company_name + title 일치)가 미지원 목록에서 제외되는지 확인
