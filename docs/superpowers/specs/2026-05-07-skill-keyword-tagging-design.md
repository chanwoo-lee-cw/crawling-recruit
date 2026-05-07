# Skill Keyword Tagging Design

**Date:** 2026-05-07

## 개요

`requirements` / `preferred_points` 텍스트를 사용자 정의 키워드 사전으로 스캔해서 `skill_tags`를 보강한다. 태그 추출은 `sync_job_details` 실행 시 자동으로 수행되며, 별도 매칭/스코어링 로직 변경 없이 기존 `get_job_candidates`의 정확도가 향상된다.

## 목표

- `requirements` / `preferred_points` 텍스트에 등장하는 기술 키워드를 `skill_tags`에 자동 병합
- 키워드 사전을 DB에 저장하고 MCP 툴로 관리
- 기존 매칭/스코어링 로직 변경 없음 (하위 호환)

## 범위 제외

- 기존 `fetched_at IS NOT NULL` 공고 재처리 (추후 별도 툴로 추가)
- LLM 기반 태그 추출
- 태그 계층 구조나 카테고리 분류

---

## 아키텍처

```
[sync_job_details 실행]
        ↓
  API에서 requirements + preferred_points + skill_tags 수집
        ↓
  skill_keywords 테이블에서 키워드 로드
  (빈 경우: 파싱 단계 건너뜀 → 기존 동작과 동일)
        ↓
  requirements + preferred_points 텍스트 스캔
  단어 경계 기준, 대소문자 무관 매칭
  기존 skill_tags에 없는 키워드만 추가
        ↓
  병합된 skill_tags를 job_details에 저장
        ↓
[get_job_candidates — 변경 없음]
  더 풍부해진 skill_tags로 기존 스코어링 수행
```

---

## DB 스키마

### 신규 테이블: `skill_keywords`

```sql
CREATE TABLE skill_keywords (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    keyword     VARCHAR(100) NOT NULL UNIQUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- `keyword`: 원본 대소문자 유지 저장, 매칭은 case-insensitive
- `UNIQUE` 제약으로 중복 등록 방지
- `job_details.skill_tags` 스키마 변경 없음

---

## 파싱 로직

`JobService.extract_keywords_from_text(text: str, keywords: list[str]) -> list[str]`

- `keywords`가 빈 경우 빈 리스트 반환
- 각 키워드에 대해 `re.search(r'\b<keyword>\b', text, re.IGNORECASE)` 로 단어 경계 매칭
- 매칭된 키워드를 원본 대소문자 그대로 반환 (사전에 저장된 형태)

**병합 규칙:**
- 기존 `skill_tags[].text`에 이미 존재하는 키워드(case-insensitive)는 추가하지 않음
- 신규 키워드는 `{"text": "<keyword>"}` 형태로 `skill_tags` 리스트에 append

---

## 신규 MCP 툴

| 툴 | 파일 | 설명 |
|---|---|---|
| `add_skill_keyword` | `tools/add_skill_keyword.py` | 키워드 1개 추가 |
| `list_skill_keywords` | `tools/list_skill_keywords.py` | 전체 키워드 목록 조회 |
| `delete_skill_keyword` | `tools/delete_skill_keyword.py` | 키워드 1개 삭제 |

### add_skill_keyword

```python
def add_skill_keyword(keyword: str) -> str
```
- 공백 trim 후 등록
- 이미 존재하면 "이미 존재하는 키워드입니다: {keyword}" 반환
- 성공 시 "키워드가 추가되었습니다: {keyword}" 반환

### list_skill_keywords

```python
def list_skill_keywords() -> str
```
- 등록된 키워드 없으면 "등록된 키워드가 없습니다." 반환
- 있으면 마크다운 목록 반환

### delete_skill_keyword

```python
def delete_skill_keyword(keyword: str) -> str
```
- 존재하지 않으면 "존재하지 않는 키워드입니다: {keyword}" 반환
- 성공 시 "키워드가 삭제되었습니다: {keyword}" 반환

---

## JobService 신규 메서드

```python
def add_keyword(self, keyword: str) -> str
def list_keywords(self) -> list[str]
def delete_keyword(self, keyword: str) -> str
def extract_keywords_from_text(self, text: str, keywords: list[str]) -> list[str]
```

툴은 얇은 래퍼, 비즈니스 로직은 `JobService`에 집중.

---

## sync_job_details 변경

`upsert_job_details` 호출 전에 파싱 단계 삽입:

```python
keywords = service.list_keywords()  # 키워드 로드 (1회)
for job_detail in fetched:
    parsed = service.extract_keywords_from_text(
        (job_detail.requirements or "") + " " + (job_detail.preferred_points or ""),
        keywords
    )
    # 기존 skill_tags에 없는 키워드만 병합
    existing = {t["text"].lower() for t in (job_detail.skill_tags or [])}
    for kw in parsed:
        if kw.lower() not in existing:
            job_detail.skill_tags = (job_detail.skill_tags or []) + [{"text": kw}]
```

키워드 목록이 비어있으면 파싱 단계 전체를 건너뜀.

---

## 변경 파일 목록

| 파일 | 변경 유형 |
|---|---|
| `db/models/skill_keyword.py` | 신규 |
| `db/connection.py` | 수정 (테이블 초기화 추가) |
| `services/jobs/job_service.py` | 수정 (메서드 4개 추가) |
| `tools/add_skill_keyword.py` | 신규 |
| `tools/list_skill_keywords.py` | 신규 |
| `tools/delete_skill_keyword.py` | 신규 |
| `tools/sync_job_details.py` | 수정 (파싱 로직 삽입) |
| `main.py` | 수정 (툴 3개 등록) |
| `tests/test_job_service.py` | 수정 (키워드 메서드 테스트 추가) |
| `tests/test_tools.py` | 수정 (새 툴 테스트 추가) |

---

## 테스트 계획

- `extract_keywords_from_text`: 단어 경계 매칭, 대소문자, 빈 텍스트, 빈 키워드 목록
- `add/list/delete_keyword`: 정상 흐름, 중복 등록, 존재하지 않는 키워드 삭제
- `sync_job_details` 통합: 키워드 있을 때 병합, 없을 때 기존 동작 유지, 중복 방지
