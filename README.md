# 원티드 미지원 채용공고 MCP 서버

Claude Code에서 자연어로 호출해 원티드에서 아직 지원하지 않은 채용공고를 찾아주는 MCP 서버.

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
WANTED_COOKIE=여기에_실제_쿠키_붙여넣기
WANTED_USER_ID=여기에_실제_user_id_입력
DB_URL=mysql+mysqlconnector://root:비밀번호@localhost:3306/recruit
ANTHROPIC_API_KEY=여기에_Anthropic_API_키_입력
```

> `ANTHROPIC_API_KEY`는 `recommend_jobs` 툴 사용 시 필요합니다. [Anthropic Console](https://console.anthropic.com)에서 발급받으세요.

#### 쿠키 & User ID 가져오기

1. [원티드](https://www.wanted.co.kr) 로그인
2. 개발자 도구 열기 (`F12` 또는 `Cmd+Option+I`)
3. **Network** 탭 → 아무 API 요청 클릭
4. **Request Headers**에서 `cookie` 값 전체 복사 → `WANTED_COOKIE`에 붙여넣기
5. **Network** 탭 → `/api/v1/applications` 요청 URL에서 `user_id=숫자` 확인 → `WANTED_USER_ID`에 입력

> **주의:** `.env` 파일은 절대 커밋하지 마세요. `.gitignore`에 이미 포함되어 있습니다.

### 4. 테이블 자동 생성

```bash
python -c "from db.connection import create_tables; create_tables()"
```

### 5. Claude Code에 MCP 서버 등록

```bash
claude mcp add wanted-jobs python /절대경로/crawling-recruit/main.py
```

예시:
```bash
claude mcp add wanted-jobs python /Users/chanwoo/PycharmProjects/crawling-recruit/main.py
```

등록 확인:
```bash
claude mcp list
# wanted-jobs: python .../main.py - ✓ Connected
```

---

## 사용법

Claude Code에서 자연어로 툴을 호출합니다.

### 채용공고 동기화

```
백엔드 개발 공고를 5페이지 동기화해줘
```
```
sync_jobs 툴로 job_group_id=518, limit_pages=5 로 동기화해줘
```

### 지원현황 동기화

```
내 원티드 지원현황 동기화해줘
```

> 쿠키가 만료된 경우: `"쿠키가 만료되었습니다. .env의 WANTED_COOKIE를 갱신해주세요."` 메시지가 반환됩니다. 위의 [쿠키 가져오기](#쿠키--user-id-가져오기) 과정을 다시 반복하세요.

### 미지원 공고 조회

```
내가 아직 지원 안 한 백엔드 공고 보여줘
```
```
서울 지역 정규직 공고 중 지원 안 한 것 20개 알려줘
```

### 검색 조건 프리셋 저장

```
save_search_preset 툴로 "백엔드 신입 서울" 이름으로 job_group_id=518, locations=서울 저장해줘
```

다음에는:
```
"백엔드 신입 서울" 프리셋으로 공고 동기화해줘
```

### 저장된 프리셋 목록

```
저장된 검색 프리셋 목록 보여줘
```

### 채용공고 상세 수집

```
최대 50개 공고의 상세 정보(요건, 우대사항, 기술태그)를 수집해줘
```
```
job_id 1234, 5678 공고 상세 정보 가져와줘
```

### 내 스택에 맞는 공고 추천

```
Python, FastAPI, MySQL 스택으로 맞는 공고 추천해줘
```
```
서울 정규직 공고 중 Python, Django 스택으로 상위 5개 추천해줘
```

> 상세 정보가 없는 공고는 자동으로 fetch하고 추천합니다 (최대 20개 lazy fetch).

---

## MCP 툴 목록

| 툴 | 파라미터 | 설명 |
|---|---|---|
| `sync_jobs` | `preset_name`, `job_group_id`, `job_ids`, `years`, `locations`, `limit_pages` | 채용공고 동기화 |
| `sync_applications` | 없음 | 지원현황 동기화 |
| `get_unapplied_jobs` | `job_group_id`, `location`, `employment_type`, `limit` | 미지원 공고 조회 |
| `save_search_preset` | `name`, `params` | 검색 조건 저장 |
| `list_search_presets` | 없음 | 저장된 프리셋 목록 |
| `sync_job_details` | `job_ids`, `limit` | 공고 상세 정보 배치 수집 |
| `recommend_jobs` | `skills`, `location`, `employment_type`, `job_group_id`, `top_n` | 기술스택 기반 공고 추천 |

---

## 권장 워크플로

처음 사용할 때:

```
1. sync_applications 으로 지원현황 먼저 동기화
2. sync_jobs 으로 채용공고 동기화 (limit_pages 없이 전체 수집 권장)
3. sync_job_details 으로 상세 정보 배치 수집 (limit=100 등)
4. recommend_jobs 으로 내 스택에 맞는 공고 추천
```

이후 정기적으로:
```
1. sync_applications 재동기화 (새 지원 반영)
2. sync_jobs 재동기화 (새 공고 반영)
3. recommend_jobs 호출 (미수집 상세 정보 자동 lazy fetch)
```

> `recommend_jobs`는 상세 정보가 없는 공고를 자동으로 최대 20개까지 수집한 뒤 추천합니다.

---

## 테스트

```bash
pytest tests/ -v
```

---

## 파일 구조

```
crawling-recruit/
├── .env                  # 실제 인증 정보 (커밋 금지)
├── .env.example          # 환경변수 템플릿
├── main.py               # MCP 서버 진입점
├── requirements.txt
├── db/
│   ├── models.py         # SQLAlchemy 테이블 정의 (jobs, applications, job_details 등)
│   └── connection.py     # DB 엔진/세션
├── services/
│   ├── wanted_client.py  # 원티드 API HTTP 클라이언트
│   └── job_service.py    # DB 동기화 비즈니스 로직
└── tools/
    ├── sync_jobs.py
    ├── sync_applications.py
    ├── get_unapplied_jobs.py
    ├── save_search_preset.py
    ├── list_search_presets.py
    ├── sync_job_details.py   # 공고 상세 정보 배치 수집
    └── recommend_jobs.py     # 기술스택 기반 공고 추천 (Claude API)
```
