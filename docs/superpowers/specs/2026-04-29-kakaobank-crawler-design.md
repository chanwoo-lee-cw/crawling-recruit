# 카카오뱅크 채용공고 크롤러 설계

**날짜:** 2026-04-29  
**소스:** kakaobank  
**범위:** 채용공고 목록 동기화 + 상세 HTML 파싱. 지원 내역 조회 없음.

---

## 1. 아키텍처 & 파일 구조

기존 NHN 패턴을 그대로 따른다.

**신규 파일:**
```
services/kakaobank/
  __init__.py
  kakaobank_constants.py     # 소스 상수, API URL 정의
  kakaobank_client.py        # 공개 API 클라이언트 (인증 불필요)
  kakaobank_syncer.py        # BaseSyncer → 목록 upsert
  kakaobank_detail_syncer.py # BaseSyncer → HTML 파싱 후 detail upsert

tools/
  kakaobank_sync_jobs.py     # MCP 툴 함수
```

**수정 파일:**
```
tools/sync_job_details.py      # kakaobank 분기 추가 + docstring 업데이트
services/jobs/job_service.py   # _parse_kakaobank_job 추가, _parse_job 분기 추가,
                               # JOB_BASE_URLS 추가, 링크 생성 예외 분기 추가
main.py                        # kakaobank_sync_jobs 등록
requirements.txt               # beautifulsoup4 추가
```

---

## 2. API 명세

**목록:** `GET https://recruit.kakaobank.com/api/recruits`
- 인증 불필요 (공개 API)
- 파라미터: `pageNumber`(0-based), `pageSize`
- 응답: `paging.totalPages`, `list[]`
- 종료 조건: `pageNumber >= totalPages` 일 때 반복 중단

**상세:** `GET https://recruit.kakaobank.com/api/recruits/{recruitNoticeSn}`
- 인증 불필요
- 응답 내 `contents` 필드: HTML 문자열

---

## 3. 데이터 매핑

### 목록 API → `jobs` 테이블

| API 필드 | DB 컬럼 | 처리 |
|---|---|---|
| `recruitNoticeSn` | `platform_id` | BigInteger |
| `recruitNoticeName` | `title` | 그대로 |
| `recruitTypeName` | `employment_type` | "일반채용" → `regular` (EMPLOYMENT_TYPE_MAP에 추가) |
| `receiveStartDatetime` | `created_at` | datetime 파싱 |
| (하드코딩) | `company_name` | `"카카오뱅크"` |
| (없음) | `location` | NULL |
| (없음) | `annual_from`, `annual_to` | NULL |
| (없음) | `company_id`, `job_group_id`, `category_tag_id` | NULL |

`_parse_job` 메서드에 `KAKAO_BANK` 분기 추가:
```python
if source == KAKAO_BANK:
    return self._parse_kakaobank_job(raw)
```

### 상세 API → `job_details` 테이블

`contents` HTML을 `BeautifulSoup(html, "html.parser")`로 파싱 (stdlib html.parser 사용, 추가 의존성 없음):

| 추출 대상 | 방법 |
|---|---|
| `requirements` | "자격요건" 섹션 텍스트 |
| `preferred_points` | "우대사항" 섹션 텍스트 |
| `skill_tags` | 빈 리스트 (HTML에서 구조화된 태그 추출 불가) |

섹션 못 찾으면 해당 필드 NULL.

### 공고 URL

카카오뱅크 URL 형식이 기존 `{base_url}/{platform_id}` 패턴과 다름. `job_service.py`에 `build_job_url(source, platform_id)` 공개 헬퍼 메서드를 추가하고, URL을 생성하는 **모든** 코드 경로에서 이 헬퍼를 사용하도록 교체:

```python
def build_job_url(self, source: str, platform_id: int) -> str:
    if source == KAKAO_BANK:
        return f"https://kakaobank.recruiter.co.kr/app/jobnotice/view?systemKindCode=MRS2&jobnoticeSn={platform_id}"
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    return f"{base_url}/{platform_id}"
```

교체 대상 코드 경로:
- `job_service.py` line 307-308: `get_unapplied_jobs` 내 인라인 URL 빌딩
- `tools/get_job_candidates.py` line 50: `JOB_BASE_URLS.get(...)/{platform_id}` 인라인 → `service.build_job_url(c.source, c.platform_id)` 로 교체

---

## 4. 동기화 흐름

```
Step 1: kakaobank_sync_jobs
  - pageNumber=0 부터 시작, pageNumber < totalPages 동안 반복
  - full_sync=True → 응답에 없는 공고 자동 is_active=False
  - 카카오뱅크 목록 API는 마감된 공고를 제외하므로 full_sync로 비활성화 정확함

Step 2: sync_job_details (source="kakaobank")
  - fetched_at IS NULL 공고만 대상
  - GET /api/recruits/{platform_id} 호출
  - 요청 사이 CRAWL_DELAY_SECONDS 대기 (NHN 패턴 동일)
  - contents HTML → BeautifulSoup(html, "html.parser") 파싱
  - job_details upsert
```

---

## 5. 에러 처리

- 인증 없음 → 로그인 실패 케이스 없음
- API 실패: `raise_for_status()` → 상위 예외 전파
- 상세 fetch 실패: 해당 공고 skip, 나머지 계속 (NHN 패턴 동일)
- HTML 섹션 미발견: 해당 필드 NULL로 저장

---

## 6. 의존성 추가

`requirements.txt`에 `beautifulsoup4` 추가.  
HTML 파서는 Python stdlib의 `html.parser` 사용 (`lxml` 불필요).
