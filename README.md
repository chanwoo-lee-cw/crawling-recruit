# 채용공고 MCP 서버 (Wanted + Remember)

superpowers+바이브 코딩으로 작성한 프로젝트
Claude Code에서 자연어로 호출해 Wanted·Remember의 미지원 채용공고를 수집하고 추천받는 MCP 서버.  
MCP 서버는 데이터 제공만 담당하고, 2차 추론·추천은 Claude Code가 직접 수행한다.

---

## 사전 준비

- Python 3.11+
- MySQL 실행 중 (로컬)
- Claude Code CLI 설치

---

## 설치

### 1. 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. MySQL DB 생성

```sql
CREATE DATABASE recruit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. `.env` 설정

`.env.example`을 복사해서 `.env`를 만들고 실제 값으로 채운다.

```bash
cp .env.example .env
```

`.env` 편집:

```
DB_URL=mysql+mysqlconnector://root:비밀번호@localhost:3306/recruit

# Wanted
WANTED_COOKIE=여기에_실제_쿠키_붙여넣기
WANTED_USER_ID=여기에_실제_user_id_입력

# Remember (선택)
REMEMBER_COOKIE=여기에_실제_쿠키_붙여넣기
REMEMBER_AUTH_TOKEN=여기에_Token_값_입력
```

#### Wanted 쿠키 & User ID 가져오기

1. [원티드](https://www.wanted.co.kr) 로그인
2. 개발자 도구 열기 (`F12` 또는 `Cmd+Option+I`)
3. **Network** 탭 → 아무 API 요청 클릭
4. **Request Headers**에서 `cookie` 값 전체 복사 → `WANTED_COOKIE`에 붙여넣기
5. **Network** 탭 → `/api/v1/applications` 요청 URL에서 `user_id=숫자` 확인 → `WANTED_USER_ID`에 입력

#### Remember 쿠키 & 토큰 가져오기

1. [리멤버 커리어](https://career.rememberapp.co.kr) 로그인
2. 개발자 도구 → **Network** 탭 → 아무 API 요청 클릭
3. **Request Headers**에서 `cookie` 값 전체 복사 → `REMEMBER_COOKIE`에 붙여넣기
4. **Request Headers**에서 `Authorization: Token token=xxx` 중 `xxx` 부분 복사 → `REMEMBER_AUTH_TOKEN`에 붙여넣기

> **주의:** `.env` 파일은 절대 커밋하지 마세요. `.gitignore`에 이미 포함되어 있습니다.

### 4. 테이블 자동 생성

```bash
python -c "from db.connection import create_tables; create_tables()"
```

또는 Claude Code에서:
```
migrate_db 툴 실행해줘
```

### 5. Claude Code에 MCP 서버 등록

```bash
claude mcp add wanted-jobs python /절대경로/crawling-recruit/main.py
```

등록 확인:
```bash
claude mcp list
# wanted-jobs: python .../main.py - ✓ Connected
```

---

## MCP 툴 목록

| 툴 | 주요 파라미터 | 설명 |
|---|---|---|
| `sync_jobs` | `source`, `preset_name`, `job_group_id`, `limit_pages` | 채용공고 동기화 (Wanted/Remember) |
| `sync_applications` | `source` | 지원현황 동기화 |
| `sync_job_details` | 없음 | 공고 상세 정보 배치 수집 (Wanted) |
| `get_unapplied_jobs` | `job_group_id`, `location`, `employment_type`, `limit` | 미지원 공고 목록 (마크다운 테이블) |
| `get_job_candidates` | `skills`, `top_n`, `include_evaluated` | skill 매칭 후보 JSON 반환 (Claude 2차 추론용) |
| `save_job_evaluations` | `evaluations` | Claude 추천 결과 verdict 저장 |
| `skip_jobs` | `job_ids`, `reason` | 공고 영구 제외 |
| `save_search_preset` | `name`, `params` | 검색 파라미터 프리셋 저장 |
| `list_search_presets` | 없음 | 저장된 프리셋 목록 조회 |
| `migrate_db` | 없음 | DB 테이블 생성/업데이트 |

---

## 자동 크롤링 (cron)

매일 오후 10시에 전체 파이프라인이 자동으로 실행된다. 결과는 `logs/daily_sync.log`에 기록된다.

```
sync_jobs(wanted) → sync_jobs(remember) → sync_job_details → sync_applications(wanted+remember)
```

새 소스 추가 시 `scripts/daily_sync.py`의 `SOURCES`와 `SYNC_CONFIG`에 항목을 추가하면 된다.

crontab 수동 확인:
```bash
crontab -l | grep daily_sync
```

---

## 권장 워크플로

### 처음 설정

```
1. migrate_db             → 테이블 생성
2. sync_applications      → 내 지원 이력 동기화 (이미 지원한 공고 제외 기준)
3. sync_jobs              → 채용공고 수집 (원티드/리멤버)
4. sync_job_details       → 공고 상세 정보 수집 (requirements, skill_tags)
5. get_job_candidates     → skill 매칭 후 Claude 2차 추천
6. save_job_evaluations   → 추천 결과 verdict 저장 (다음 세션에서 재처리 방지)
```

### 이후 정기 사용

자동 크롤링이 매일 22:00에 실행되므로, Claude Code에서 추천만 받으면 된다:

```
1. get_job_candidates     → 미평가 공고만 추천 (이미 평가한 공고 자동 제외)
2. save_job_evaluations   → verdict 저장
```

### 이미 평가한 공고 다시 보기

```
get_job_candidates(skills=[...], include_evaluated=True)
```

---

## 사용 예시

```
# 공고 동기화
원티드 백엔드 공고 20페이지 동기화해줘
리멤버에서 백엔드 3~5년차 공고 동기화해줘

# 미지원 공고 조회
내가 아직 지원 안 한 서울 정규직 공고 보여줘

# 추천
Python, Kotlin 스택으로 3~5년차가 지원할 만한 공고 10개 추천해줘

# 공고 제외
job_id 714, 715 공고는 관심 없어. 연봉 낮음 이유로 제외해줘

# 프리셋 저장
"백엔드 경력" 이름으로 source=remember, min_experience=3, max_experience=5 프리셋 저장해줘
```

---

## 파일 구조

```
crawling-recruit/
├── .env                      # 실제 인증 정보 (커밋 금지)
├── .env.example              # 환경변수 템플릿
├── main.py                   # MCP 서버 진입점 및 툴 등록
├── constants.py              # CRAWL_DELAY_SECONDS, DEFAULT_LIMIT_PAGES
├── domain.py                 # 도메인 데이터클래스 (JobCandidate, JobDetail 등)
├── requirements.txt
├── db/
│   ├── models.py             # SQLAlchemy 테이블 정의
│   └── connection.py         # DB 엔진/세션/테이블 생성
├── services/
│   ├── wanted_client.py      # Wanted API 클라이언트
│   ├── remember_client.py    # Remember API 클라이언트
│   └── job_service.py        # DB CRUD 및 추천 로직
├── scripts/
│   └── daily_sync.py         # 자동 크롤링 cron 러너
├── tools/
│   ├── sync_jobs.py
│   ├── sync_applications.py
│   ├── sync_job_details.py
│   ├── get_unapplied_jobs.py
│   ├── get_job_candidates.py
│   ├── save_job_evaluations.py
│   ├── skip_jobs.py
│   ├── save_search_preset.py
│   ├── list_search_presets.py
│   └── migrate_db.py
├── tests/
│   ├── test_job_service.py
│   ├── test_tools.py
│   ├── test_db.py
│   ├── test_daily_sync.py
│   └── test_wanted_client.py
├── spec/                     # 도메인별 요구사항 및 설계 문서
│   ├── jobs/
│   ├── applications/
│   ├── job-details/
│   ├── search-presets/
│   ├── job-skip/
│   └── job-evaluation/
└── doc/                      # 외부 API 문서
    ├── wanted.md
    └── remember.md
```

---

## DB 스키마 요약

| 테이블 | 설명 |
|--------|------|
| `jobs` | 수집된 채용공고 (Wanted + Remember) |
| `job_details` | 공고 상세 (requirements, skill_tags 등) |
| `applications` | 내 지원 이력 |
| `job_skips` | 수동 제외 공고 |
| `job_evaluations` | Claude 추천 verdict 캐시 (`good`/`pass`/`skip`) |
| `search_presets` | 저장된 검색 파라미터 |

---

## 테스트

```bash
pytest
```
