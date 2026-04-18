# 공고 상세(Job Detail) 설계

## 스키마

```
job_details
├── job_id          INT PK FK→jobs.internal_id ON DELETE CASCADE
├── requirements    TEXT NULL        -- 자격요건 원문
├── preferred_points TEXT NULL       -- 우대사항 원문
├── skill_tags      JSON NULL        -- [{"text": "Python"}, ...]
└── fetched_at      DATETIME NOT NULL
```

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `sync_job_details` | 상세 미수집 공고 크롤링 | 없음 (미수집 전체 자동 처리) |

## 데이터 흐름

```
JobService.get_jobs_without_details()
    → [job_id, ...]  (job_details 레코드 없는 공고)

for each job_id:
    WantedClient.fetch_job_detail(job_id)
    → JobDetail(job_id, requirements, preferred_points, skill_tags)
    time.sleep(CRAWL_DELAY_SECONDS)

JobService.upsert_job_details([JobDetail, ...])
    → job_details INSERT
```

## skill_tags 구조

```json
[
  {"text": "Python"},
  {"text": "Django"},
  {"text": "백엔드"}
]
```

Claude의 `get_recommended_jobs`가 이 태그와 사용자 입력 skills를 비교해 점수를 산출한다.

## 에러 처리

| 상황 | 처리 |
|------|------|
| fetch_job_detail이 None 반환 | 해당 job_id 건너뜀, 다음 공고 진행 |
| 네트워크 오류 | 예외 캐치 후 건너뜀 (로그 없음) |
| 미수집 공고 0개 | `"처리할 공고가 없습니다."` 반환 |
