# 쿠팡 · 카카오뱅크 · 우아한형제들 채용공고 크롤러 설계

**날짜:** 2026-05-02  
**소스:** coupang, kakaobank, woowahan  
**범위:** 채용공고 목록 + 상세 동기화. 지원현황은 쿠팡·카카오뱅크 없음, 우아한형제들은 로그인 인증 기반 구현.

> 카카오뱅크는 `2026-04-29-kakaobank-crawler-design.md` 기존 스펙을 기반으로 이 문서에 통합한다.

---

## 1. 아키텍처 & 파일 구조

기존 `services/<source>/` 패턴을 동일하게 적용한다.

**신규 파일:**
```
services/
  coupang/
    __init__.py
    coupang_constants.py
    coupang_client.py            # HTML 스크래핑 (리스트 + 상세)
    coupang_syncer.py
    coupang_detail_syncer.py     # BeautifulSoup 파싱
    coupang_application_syncer.py  # "미지원 정보 없음" 반환

  kakaobank/
    __init__.py
    kakaobank_constants.py
    kakaobank_client.py          # JSON API (리스트 + 상세 HTML)
    kakaobank_syncer.py
    kakaobank_detail_syncer.py   # BeautifulSoup 파싱
    kakaobank_application_syncer.py  # "미지원 정보 없음" 반환

  woowahan/
    __init__.py
    woowahan_constants.py
    woowahan_client.py           # JSON API + 로그인/쿠키 인증
    woowahan_syncer.py
    woowahan_detail_syncer.py    # BeautifulSoup 파싱
    woowahan_application_syncer.py  # 로그인 후 지원현황 조회

tools/
  coupang_sync_jobs.py
  kakaobank_sync_jobs.py
  woowahan_sync_jobs.py

tests/
  test_coupang_client.py
  test_coupang_syncer.py
  test_coupang_detail_syncer.py
  test_kakaobank_client.py
  test_kakaobank_syncer.py
  test_kakaobank_detail_syncer.py
  test_woowahan_client.py
  test_woowahan_syncer.py
  test_woowahan_detail_syncer.py
  test_woowahan_application_syncer.py
```

**수정 파일:**
```
services/jobs/job_service.py   # _parse_<source>_job 3개 추가, _parse_job 분기, JOB_BASE_URLS
tools/sync_job_details.py      # 3개 소스 분기 추가
tools/sync_applications.py     # 3개 소스 분기 추가
scripts/daily_sync.py          # 3개 소스 추가
main.py                        # 3개 툴 등록
```

---

## 2. 소스별 API 명세

### 2-1. 쿠팡

**리스트:** HTML 스크래핑
```
GET https://www.coupang.jobs/kr/jobs/?search=&location=South+Korea&pagesize=500
```
- 단일 요청으로 전체 수집 (`pagesize=500` 설정)
- 수집 후 `len(jobs) >= 500`이면 경고 로그 출력 (향후 페이지네이션 추가 신호)
- 파싱 대상: `div.card.card-job` 반복
  - job_id: `div.card-job-actions.js-job[data-id]`
  - title: `h2.card-title a.js-view-job` 텍스트
  - location: `ul.list-inline li.list-inline-item` 첫 번째 텍스트

**상세:** HTML 스크래핑
```
GET https://www.coupang.jobs/kr/jobs/{job_id}
```
- 파싱 대상: `div.main-col article.cms-content`
- 섹션 추출: `<strong>` 태그 텍스트로 섹션 시작점 감지
  - `"자격 요건"` 포함 → `requirements`
  - `"우대 사항"` 포함 → `preferred_points`
  - 각 섹션 이후 `<ul>` 내 `<li>` 텍스트 결합

**지원현황:** 미지원 → `"쿠팡은 지원현황 API를 지원하지 않습니다."`

---

### 2-2. 카카오뱅크

**리스트:** JSON API
```
GET https://recruit.kakaobank.com/api/recruits?pageSize=20&pageNumber={n}
```
- 0-based pageNumber, `paging.totalPages` 기준으로 전 페이지 순회
- 마감 공고는 API가 자동 제외 → `full_sync=True` 적용 가능

**상세:** JSON API
```
GET https://recruit.kakaobank.com/api/recruits/{recruitNoticeSn}
```
- `contents` 필드(HTML 문자열) 파싱
- HTML 구조: `div.desc_cont` 반복, 각 블록 `div.tit`(섹션명) + `div.cont`(내용)
  - `"필수 경험과 역량"` → `requirements`
  - `"우대사항"` → `preferred_points`
  - `div.cont` 내 `<p>` 태그 텍스트 줄바꿈 결합

**지원현황:** 미지원 → `"카카오뱅크는 지원현황 API를 지원하지 않습니다."`

---

### 2-3. 우아한형제들

**리스트:** JSON API
```
GET https://career.woowahan.com/w1/recruits?jobGroupCodes={codes}&recruitCampaignSeq=0&page={n}&size=100&sort=updateDate,desc
```
- 기본값: `jobGroupCodes=BA005001` (개발직군), 파라미터로 변경 가능
- `data.totalPageNumber` 기준으로 전 페이지 순회
- `platform_id = int(recruit_number[1:])`: `recruitNumber`(예: `"R2411018"`)에서 `"R"` 제거 후 int 변환 → `2411018`

**상세:** JSON API
```
GET https://career.woowahan.com/w1/recruits/{recruitNumber}
```
- `platform_id`(int, 예: `2411018`) → `recruitNumber` 복원: `f"R{platform_id}"` → `"R2411018"`
- `data.recruitContents` 필드(HTML 문자열) 파싱
- 섹션 추출: `<strong>` 태그 텍스트 패턴 감지
  - `"[지원자격]"` → `requirements`
  - `"[우대사항]"` → `preferred_points`

**지원현황:** 로그인 기반
```
POST https://career.woowahan.com/login
Body: {"applicantEmail": ..., "applicantPassword": ...}
→ Set-Cookie: X-Authorization=<jwt>

GET https://career.woowahan.com/w1/applications?page=0&size=100&sort=applicationDate,desc
Cookie: X-Authorization=<jwt>
```
- 인증정보: `.env`의 `WOOWAHAN_EMAIL`, `WOOWAHAN_PASSWORD`
- 응답 `code`가 `"2101"` (비밀번호 만료 경고)이어도 쿠키가 발급되면 진행
- 로그인 실패 시 한국어 에러 반환

---

## 3. 데이터 매핑

### `job_service.py` 추가 메서드

#### `_parse_coupang_job(raw)`
| 필드 | DB 컬럼 | 처리 |
|------|---------|------|
| `id` | `platform_id` | int |
| `title` | `title` | 그대로 |
| `location` | `location` | 텍스트 (예: "대한민국") |
| (고정) | `company_name` | `"Coupang"` |
| (없음) | `employment_type`, `annual_from`, `annual_to` | NULL |
| (없음) | `created_at` | NULL |
| (고정) | `is_active` | `True` |
| (현재시각) | `synced_at` | `datetime.now(timezone.utc)` |
| (고정) | `updated_at` | `None` |

#### `_parse_kakaobank_job(raw)`
| 필드 | DB 컬럼 | 처리 |
|------|---------|------|
| `recruitNoticeSn` | `platform_id` | int |
| `recruitNoticeName` | `title` | 그대로 |
| `recruitTypeName` | `employment_type` | EMPLOYMENT_TYPE_MAP 적용 |
| `receiveStartDatetime` | `created_at` | datetime 파싱 |
| (고정) | `company_name` | `"카카오뱅크"` |
| (없음) | `location`, `annual_from`, `annual_to` | NULL |
| (고정) | `is_active` | `True` |
| (현재시각) | `synced_at` | `datetime.now(timezone.utc)` |
| (고정) | `updated_at` | `None` |

#### `_parse_woowahan_job(raw)`
| 필드 | DB 컬럼 | 처리 |
|------|---------|------|
| `recruitNumber` | `platform_id` | `int(recruit_number[1:])` — `"R2411018"` → `2411018` |
| `recruitName` | `title` | 그대로 |
| `employmentType.recruitItemCode` | `employment_type` | `BA002001` → `"regular"` 등 매핑 |
| `recruitOpenDate` | `created_at` | datetime 파싱 |
| (고정) | `company_name` | `"우아한형제들"` |
| (없음) | `location`, `annual_from`, `annual_to` | NULL |
| (고정) | `is_active` | `True` |
| (현재시각) | `synced_at` | `datetime.now(timezone.utc)` |
| (고정) | `updated_at` | `None` |

### `JOB_BASE_URLS` 추가

```python
COUPANG = "coupang"
KAKAO_BANK = "kakaobank"
WOOWAHAN = "woowahan"

JOB_BASE_URLS = {
    ...
    COUPANG: "https://www.coupang.jobs/kr/jobs",
    KAKAO_BANK: "https://kakaobank.recruiter.co.kr/app/jobnotice/view?systemKindCode=MRS2&jobnoticeSn=",
    WOOWAHAN: "https://career.woowahan.com/recruit",
}
```

카카오뱅크 URL은 `base_url.endswith("=")` 조건을 활용해 기존 `build_job_url` 분기 없이 처리된다:
```python
# 기존 build_job_url 로직 그대로 적용됨
if base_url.endswith("="):
    return f"{base_url}{platform_id}"  # → ?jobnoticeSn=251760
```

---

## 4. 동기화 흐름

```
[쿠팡]
Step 1: coupang_sync_jobs
  - pagesize=500 단일 요청, full_sync=True
  - len(jobs) >= 500이면 경고 로그
Step 2: sync_job_details(source="coupang")
  - fetched_at IS NULL 공고 순회
  - CRAWL_DELAY_SECONDS 대기
Step 3: sync_applications(source="coupang")
  - "쿠팡은 지원현황 API를 지원하지 않습니다." 즉시 반환

[카카오뱅크]
Step 1: kakaobank_sync_jobs
  - pageNumber=0 부터 totalPages 미만 동안 반복, full_sync=True
Step 2: sync_job_details(source="kakaobank")
  - fetched_at IS NULL 공고 순회
Step 3: sync_applications(source="kakaobank")
  - "카카오뱅크는 지원현황 API를 지원하지 않습니다." 즉시 반환

[우아한형제들]
Step 1: woowahan_sync_jobs
  - jobGroupCodes=BA005001 기본값, page=0 부터 totalPageNumber 미만 순회
  - full_sync=True
Step 2: sync_job_details(source="woowahan")
  - fetched_at IS NULL 공고 순회
  - platform_id(int) → f"R{platform_id}" → recruitNumber → 상세 API 호출
  - CRAWL_DELAY_SECONDS 대기
Step 3: sync_applications(source="woowahan")
  - WOOWAHAN_EMAIL/PASSWORD로 로그인 → X-Authorization 쿠키 획득
  - GET /w1/applications 전 페이지 순회
```

---

## 5. 에러 처리

| 상황 | 처리 |
|------|------|
| HTML 스크래핑 실패 (쿠팡) | `raise_for_status()` → 예외 전파 |
| 상세 fetch 실패 | 해당 공고 skip, 나머지 계속 |
| HTML 섹션 미발견 | 해당 필드 NULL 저장 |
| 우아한형제들 로그인 실패 | 한국어 에러 문자열 반환 |
| 우아한형제들 비밀번호 만료 경고 (`code=2101`) | 쿠키 발급되면 계속 진행 |
| `.env` 환경변수 누락 (woowahan) | `ValueError` raise → 한국어 에러 반환 |

---

## 6. 환경변수 (.env)

```
WOOWAHAN_EMAIL=...
WOOWAHAN_PASSWORD=...
```

---

## 7. 테스트 전략

- 모든 네트워크 호출은 `unittest.mock.patch` 또는 고정 fixture로 mock 처리
- 쿠팡: 실제 HTML 샘플(doc 기반)로 `_parse_coupang_detail` unit test
- 카카오뱅크: 실제 JSON + HTML contents 샘플로 `_parse_kakaobank_detail` unit test
- 우아한형제들 detail syncer:
  - `platform_id = 2411018` → `f"R{platform_id}"` → `"R2411018"` 상세 API 호출 확인
- 우아한형제들 application syncer: 로그인 → 쿠키 → 지원현황 조회 흐름 mock 검증
- `daily_sync.py` 통합: 3개 소스가 모두 호출되는지 확인

---

## 8. 통합 등록

### `main.py` 툴 등록

```python
from tools.coupang_sync_jobs import coupang_sync_jobs
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs
from tools.woowahan_sync_jobs import woowahan_sync_jobs

mcp.tool()(coupang_sync_jobs)
mcp.tool()(kakaobank_sync_jobs)
mcp.tool()(woowahan_sync_jobs)
```

### `daily_sync.py` 통합

기존 소스 목록에 3개 추가:

```python
from services.coupang.coupang_syncer import CoupangSyncer
from services.coupang.coupang_detail_syncer import CoupangDetailSyncer
from services.coupang.coupang_application_syncer import CoupangApplicationSyncer
from services.kakaobank.kakaobank_syncer import KakaoBankSyncer
from services.kakaobank.kakaobank_detail_syncer import KakaoBankDetailSyncer
from services.kakaobank.kakaobank_application_syncer import KakaoBankApplicationSyncer
from services.woowahan.woowahan_syncer import WoowahanSyncer
from services.woowahan.woowahan_detail_syncer import WoowahanDetailSyncer
from services.woowahan.woowahan_application_syncer import WoowahanApplicationSyncer
```
