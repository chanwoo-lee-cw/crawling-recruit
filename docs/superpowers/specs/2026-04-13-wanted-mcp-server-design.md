# 원티드 미지원 채용공고 MCP 서버 설계

**날짜:** 2026-04-13  
**스택:** Python 3.11, fastmcp, httpx, SQLAlchemy Core, MySQL

---

## 개요

원티드 채용공고 API와 지원현황 API를 활용해, 현재 지원하지 않은 채용공고를 찾아주는 MCP 서버. Claude Code에서 자연어로 호출 가능하며, 채용공고와 지원현황을 MySQL DB에 저장해 빠른 조회와 히스토리 관리를 지원한다.

---

## 아키텍처

```
crawling-recruit/
├── .env                        # 쿠키, DB 연결 정보 (커밋 금지)
├── main.py                     # MCP 서버 진입점
├── db/
│   ├── connection.py           # SQLAlchemy 엔진/세션
│   └── models.py               # 테이블 정의
├── services/
│   ├── wanted_client.py        # httpx로 원티드 API 호출
│   └── job_service.py          # 동기화/필터링 비즈니스 로직
└── tools/
    ├── sync_jobs.py            # MCP 툴: 채용공고 동기화
    ├── sync_applications.py    # MCP 툴: 지원현황 동기화
    ├── get_unapplied_jobs.py   # MCP 툴: 미지원 공고 조회
    ├── save_search_preset.py   # MCP 툴: 검색 프리셋 저장
    └── list_search_presets.py  # MCP 툴: 프리셋 목록 조회
```

### 데이터 흐름

1. Claude → `sync_jobs` 호출 → `wanted_client`로 원티드 채용공고 API 페이징 수집 → DB upsert
2. Claude → `sync_applications` 호출 → 지원한 공고 전체 수집 → DB 저장
3. Claude → `get_unapplied_jobs` 호출 → `jobs LEFT JOIN applications WHERE a.job_id IS NULL` 쿼리 → 결과 반환

---

## API 페이지네이션

### 채용공고 API
- 요청 파라미터: `limit=20`, `offset=0`
- 응답의 `links.next` 필드에 다음 페이지 경로가 포함됨. `links.next`가 `null`이면 마지막 페이지.
- `sync_jobs`는 `offset`을 20씩 증가시키며 `limit_pages`에 도달하거나 `links.next`가 null이 될 때까지 반복.

### 지원현황 API
- 요청 파라미터: `limit=10`, `offset=0`, `page=1`
- 응답의 `links.next`가 null이면 마지막 페이지.
- 응답의 `total` 필드로 전체 건수 파악 가능.
- `sync_applications`는 `links.next`가 null이 될 때까지 모든 페이지를 수집.

---

## DB 스키마

```sql
-- 채용공고
CREATE TABLE jobs (
    id              INT PRIMARY KEY,        -- 원티드 공고 ID (API의 id 필드)
    company_id      INT NOT NULL,
    company_name    VARCHAR(255) NOT NULL,
    title           VARCHAR(255) NOT NULL,  -- 포지션 (API의 position 필드)
    location        VARCHAR(100),
    employment_type VARCHAR(50),            -- regular 등
    annual_from     INT,
    annual_to       INT,
    job_group_id    INT,                    -- 직군 ID (예: 518 = 개발)
    category_tag_id INT,                    -- 세부 직무 ID (예: 872)
    is_active       BOOLEAN DEFAULT TRUE,   -- 공고 활성화 여부
    created_at      DATETIME,              -- 원티드에 등록된 시각
    synced_at       DATETIME NOT NULL,     -- 마지막 동기화 시각
    updated_at      DATETIME               -- 필드 값이 변경된 시각
);

-- 지원현황
CREATE TABLE applications (
    id          INT PRIMARY KEY,           -- 원티드 application ID
    job_id      INT NOT NULL,              -- jobs.id 참조
    status      VARCHAR(50) NOT NULL,      -- complete, pass, hire, reject
    apply_time  DATETIME,
    synced_at   DATETIME NOT NULL
);

-- 검색 프리셋
CREATE TABLE search_presets (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,  -- 중복 이름 불허
    params     JSON NOT NULL,                 -- sync_jobs 파라미터와 동일한 키 사용
    created_at DATETIME NOT NULL
);
-- Upsert 전략: 충돌 키 = name. 충돌 시 params와 created_at을 현재 값으로 덮어씀.
```

**핵심 조회 쿼리 (미지원 공고):**
```sql
SELECT j.* FROM jobs j
LEFT JOIN applications a ON j.id = a.job_id
WHERE a.job_id IS NULL
  AND j.is_active = TRUE
```

### Upsert 전략 (`jobs` 테이블)

- 충돌 키: `id` (PRIMARY KEY)
- 충돌 시 업데이트 컬럼: `company_name`, `title`, `location`, `employment_type`, `annual_from`, `annual_to`, `is_active`, `synced_at`
- `updated_at` 갱신: MySQL `ON DUPLICATE KEY UPDATE`의 `IF` 표현식으로 처리:
  ```sql
  updated_at = IF(
    company_name <> VALUES(company_name) OR title <> VALUES(title) OR
    location <> VALUES(location) OR employment_type <> VALUES(employment_type) OR
    annual_from <> VALUES(annual_from) OR annual_to <> VALUES(annual_to),
    NOW(), updated_at
  )
  ```
- `created_at`은 충돌 시 덮어쓰지 않음 (최초 등록 시각 보존)

### Upsert 전략 (`applications` 테이블)

- 충돌 키: `id` (PRIMARY KEY)
- 충돌 시 업데이트 컬럼: `status`, `synced_at`
- `apply_time`은 충돌 시 덮어쓰지 않음 (최초 지원 시각 보존)

### 공고 비활성화 (`is_active`) 전략

전체 동기화(`limit_pages` 제한 없이 모든 페이지 수집) 시에만 비활성화 처리를 수행:
- 해당 sync 요청 파라미터 조건으로 수집된 공고 ID 집합을 구성
- DB에 이미 존재하지만 이번 수집 결과에 없는 공고 ID는 `is_active = FALSE`로 업데이트
- `limit_pages`가 지정된 부분 동기화는 비활성화 처리를 수행하지 않음 (일부 페이지만 수집했으므로 없는 공고가 마감됐다고 단정할 수 없음)

---

## MCP 툴 인터페이스

### `sync_jobs`
채용공고를 원티드 API에서 수집해 DB에 upsert한다.

| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| preset_name | str (선택) | - | 저장된 프리셋 이름 (지정 시 다른 파라미터 무시) |
| job_group_id | int (선택) | 518 | 직군 ID |
| job_ids | list[int] (선택) | - | 세부 직무 ID 목록 |
| years | list[int] (선택) | - | 경력 범위 |
| locations | str (선택) | "all" | 지역 |
| limit_pages | int (선택) | - | 최대 수집 페이지 수. 미지정(None) 시 전체 수집 |

반환: `"동기화 완료: 신규 42개, 변경 13개, 유지 100개"`  
(신규 = 새로 추가된 공고, 변경 = 필드 값이 바뀐 공고, 유지 = 변경 없는 공고)

### `sync_applications`
지원한 공고 전체를 수집해 DB에 저장한다. 쿠키는 `.env`에서 자동 로드.

반환: `"지원현황 동기화 완료: 총 554건"`  
에러 (HTTP 401/403): `"쿠키가 만료되었습니다. .env의 WANTED_COOKIE를 갱신해주세요."`  
※ 빈 결과는 쿠키 만료로 간주하지 않음. HTTP 상태 코드로만 만료 판별.

### `get_unapplied_jobs`
DB에서 미지원 공고를 조회한다.

| 파라미터 | 타입 | 기본값 | DB 컬럼 | 설명 |
|---|---|---|---|---|
| job_group_id | int (선택) | - | `jobs.job_group_id` | 직군 필터 |
| location | str (선택) | - | `jobs.location` | 지역 필터 (예: "서울", "경기") |
| employment_type | str (선택) | - | `jobs.employment_type` | 고용형태 필터 (예: "regular") |
| limit | int (선택) | 20 | - | 최대 결과 수 |

적용되는 SQL 필터 (선택적 추가):
```sql
AND j.job_group_id = :job_group_id   -- job_group_id 지정 시
AND j.location LIKE CONCAT('%', :location, '%')  -- location 지정 시 (부분 일치)
AND j.employment_type = :employment_type  -- employment_type 지정 시
```

반환: Markdown 테이블 형식의 문자열

```
| 회사명 | 포지션 | 지역 | 링크 |
|---|---|---|---|
| 위버스컴퍼니 | Back-end Engineer | 경기 성남시 | https://www.wanted.co.kr/wd/353354 |
...
총 N개의 미지원 공고
```

### `save_search_preset`
자주 쓰는 검색 조건을 이름과 함께 DB에 저장한다. `params` 키는 `sync_jobs`의 파라미터 목록으로 제한하며, 유효하지 않은 키가 포함된 경우 에러를 반환한다.

| 파라미터 | 타입 | 설명 |
|---|---|---|
| name | str | 프리셋 이름 (예: "백엔드 신입 서울"). 중복 시 덮어씀 |
| params | dict | sync_jobs 파라미터 (job_group_id, job_ids, years, locations, limit_pages) |

반환: `"프리셋 '백엔드 신입 서울' 저장 완료"`  
에러 (유효하지 않은 키): `"유효하지 않은 파라미터 키: ['invalid_key']. 허용 키: job_group_id, job_ids, years, locations, limit_pages"`

### `list_search_presets`
저장된 검색 프리셋 목록을 반환한다. 입력 파라미터 없음.

반환: `"저장된 프리셋: 백엔드 신입 서울, 프론트엔드 전체"` (없으면 `"저장된 프리셋이 없습니다."`)

---

## 인증

`.env`에 저장:
```
WANTED_COOKIE=_fwb=...; WWW_ONEID_ACCESS_TOKEN=...
WANTED_USER_ID=1213478
DB_URL=mysql+mysqlconnector://root:1234@localhost:3306/demo
```

`sync_applications` 호출 시 `WANTED_COOKIE`를 `Cookie` 헤더에, `WANTED_USER_ID`를 API 경로 파라미터로 사용. HTTP 401/403 응답 시 만료로 간주하고 갱신 안내 메시지를 반환한다.

---

## 에러 처리

| 상황 | 처리 |
|---|---|
| 쿠키 만료 (HTTP 401/403) | 에러 메시지 + `.env` 갱신 안내 |
| 원티드 API rate limit (429) | `Retry-After` 헤더 값(초) 대기 후 재시도. 헤더 없으면 1초 대기. 최대 3회 |
| DB 연결 실패 | 에러 메시지 반환 |
| 페이징 중단 (`limit_pages` 도달) | 수집된 데이터까지 upsert 후 완료 보고. 비활성화 처리는 수행하지 않음 |

---

## 보안

- `.env`는 절대 커밋하지 않는다 (`.gitignore`에 포함).
- 쿠키, 토큰, DB 비밀번호는 모두 `.env`에서만 관리한다.
