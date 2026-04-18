# 지원현황(Application) 설계

## 스키마

```
applications
├── internal_id   INT PK AUTO_INCREMENT
├── source        VARCHAR(20) NOT NULL  -- "wanted" | "remember"
├── platform_id   INT NOT NULL          -- 플랫폼별 지원 ID
├── job_id        INT NOT NULL FK→jobs.internal_id
├── status        VARCHAR(50) NOT NULL  -- "complete", "pass", ...
├── apply_time    DATETIME NULL
├── synced_at     DATETIME NOT NULL
└── UNIQUE(source, platform_id)
```

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `sync_applications` | 지원 이력 수집 | `source` ("wanted" \| "remember") |

## 데이터 흐름

```
외부 API (Wanted/Remember)
    ↓ fetch_applications()
WantedClient / RememberClient
    ↓ raw dict list
JobService.upsert_applications(apps, source)
    ↓ 공고 매핑 (platform_id → jobs.internal_id)
    ↓ INSERT ... ON DUPLICATE KEY UPDATE
applications 테이블
```

## 미지원 공고 필터링 로직

`get_unapplied_jobs` / `get_job_candidates` 공통으로 아래 서브쿼리 사용:

```sql
WHERE (company_name, title) NOT IN (
    SELECT jobs.company_name, jobs.title
    FROM jobs JOIN applications ON jobs.internal_id = applications.job_id
)
```

platform_id 기준이 아닌 (company_name, title) 기준을 사용하는 이유:
동일 공고가 플랫폼별로 다른 platform_id를 가질 수 있기 때문.

## 에러 처리

| 상황 | 처리 |
|------|------|
| Wanted 쿠키 만료 | `"쿠키가 만료되었습니다."` 포함 문자열 반환 |
| Remember 쿠키 만료 (401/403) | `"Remeber 쿠키가 만료되었습니다."` 포함 문자열 반환 |
| REMEMBER_COOKIE 미설정 | `ValueError` → 안내 문자열 반환 |
