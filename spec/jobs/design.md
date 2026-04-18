# 채용공고(Job) 설계

## 스키마

```
jobs
├── internal_id   INT PK AUTO_INCREMENT
├── source        VARCHAR(20) NOT NULL  -- "wanted" | "remember"
├── platform_id   INT NOT NULL
├── company_id    INT NULL
├── company_name  VARCHAR(255) NOT NULL
├── title         VARCHAR(255) NOT NULL
├── location      VARCHAR(100) NULL
├── employment_type VARCHAR(50) NULL   -- "regular" | "intern" | "contract"
├── annual_from   INT NULL
├── annual_to     INT NULL
├── job_group_id  INT NULL
├── category_tag_id INT NULL
├── is_active     BOOLEAN DEFAULT TRUE
├── created_at    DATETIME NULL
├── synced_at     DATETIME NOT NULL
├── updated_at    DATETIME NULL
└── UNIQUE(source, platform_id)
```

## MCP 툴

| 툴 | 설명 | 주요 파라미터 |
|----|------|-------------|
| `sync_jobs` | 외부 플랫폼 공고 수집 | `source`, `preset_name`, `job_group_id`, `limit_pages` |
| `get_unapplied_jobs` | 미지원 공고 마크다운 테이블 반환 | `job_group_id`, `location`, `employment_type`, `limit` |
| `get_job_candidates` | skill 매칭 후보 JSON 반환 (Claude 2차 추론용) | `skills`, `top_n`, `include_evaluated` |

## Source별 URL

| source | 공고 URL 패턴 |
|--------|-------------|
| wanted | `https://www.wanted.co.kr/wd/{platform_id}` |
| remember | `https://career.rememberapp.co.kr/job/posting/{platform_id}` |

## 데이터 흐름

```
외부 API (Wanted/Remember)
    ↓ fetch_jobs()
WantedClient / RememberClient
    ↓ raw dict list
JobService.upsert_jobs(jobs, source, full_sync)
    ↓ INSERT ... ON DUPLICATE KEY UPDATE
jobs 테이블
    ↓ (full_sync=True 시) is_active=False 마킹 — 목록에 없는 공고
```

## 에러 처리

| 상황 | 처리 |
|------|------|
| preset_name 없음 | `"프리셋 '{name}'을 찾을 수 없습니다."` 반환 |
| Remember job_category_names 누락 | `"Remeber 동기화에는 job_category_names가 필요합니다."` 반환 |
| 쿠키 만료 (401/403) | `PermissionError` → 한국어 안내 문자열 반환 |
