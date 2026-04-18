# Job Evaluation Cache 설계

## 배경

`get_job_candidates` 호출 시 Claude가 매번 동일한 공고를 다시 읽으며 토큰을 소비한다. 이미 평가한 공고의 결과를 DB에 저장해 다음 세션에서 재처리하지 않도록 한다.

## 목표

- Claude가 평가한 공고를 `job_evaluations` 테이블에 저장
- `get_job_candidates`가 이미 평가된 공고를 기본 제외
- Claude는 매 세션 미평가 공고만 읽어 토큰 절약

## 데이터 모델

### `job_evaluations` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `job_id` | INT PK FK→jobs.internal_id | 공고 식별자 (CASCADE DELETE) |
| `verdict` | VARCHAR(20) | `"good"` / `"pass"` / `"skip"` |
| `evaluated_at` | DATETIME | 평가 시각 |

- `job_id`가 PK → 공고당 평가 하나
- `"good"`: Claude가 지원 고려 대상으로 추천한 공고
- `"pass"`: 읽었지만 현재 조건에 맞지 않는 공고
- `"skip"`: 영구 제외 (사용자가 나중에 수동 skip과 구분하기 위한 예약)

## 변경 범위

### 1. `db/models.py` — `JobEvaluation` 모델 추가

`Job` 클래스에 relationship 추가 (`JobSkip.skip` 패턴과 동일):
```python
evaluation: Mapped[Optional["JobEvaluation"]] = relationship(back_populates="job", uselist=False)
```

새 모델:
```python
class JobEvaluation(Base):
    __tablename__ = "job_evaluations"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="evaluation")
```

`Base.metadata.create_all`이 자동으로 테이블을 생성하므로 별도 마이그레이션 불필요. 단, 기존 DB에는 `create_tables()`를 한 번 실행해야 한다.

### 2. `services/job_service.py`

**`get_unapplied_job_rows` 수정**: `LEFT JOIN job_evaluations` 추가, `include_evaluated: bool = False` 파라미터 추가.

- `include_evaluated=False`(기본): `job_evaluations.job_id IS NULL`인 공고만 반환
- `include_evaluated=True`: 평가 여부 무관하게 반환

**`save_job_evaluations` 메서드 추가**:

```python
def save_job_evaluations(self, evaluations: list[dict]) -> str:
    # evaluations: [{"job_id": int, "verdict": str}, ...]
    # verdict가 "good"/"pass"/"skip"이 아닌 경우 ValueError
    # evaluated_at은 서버 측 datetime.now(timezone.utc) 사용 (skip_jobs 패턴 동일)
    # on_duplicate_key_update로 upsert (재평가 가능)
```

### 3. `tools/get_job_candidates.py` — 수정

두 가지 변경:
1. 반환 JSON에 `"job_id": c.internal_id` 추가 — Claude가 `save_job_evaluations` 호출 시 필요
2. `include_evaluated: bool = False` 파라미터 추가 → `get_unapplied_job_rows`에 전달

```python
def get_job_candidates(
    skills: list[str],
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    top_n: int = 30,
    include_evaluated: bool = False,
) -> str:
```

반환 JSON 예시:
```json
{"job_id": 744, "url": "https://...", "company_name": "랭디", ...}
```

### 4. `tools/save_job_evaluations.py` — 새 MCP 툴

```python
def save_job_evaluations(evaluations: list[dict]) -> str:
    """Claude가 평가한 공고 verdict를 저장한다.

    evaluations: [{"job_id": int, "verdict": "good"|"pass"|"skip"}, ...]
    - good: 지원 고려 대상
    - pass: 이번엔 해당 없음 (다음 세션에서 다시 나오지 않음)
    - skip: 영구 제외
    get_job_candidates는 이미 평가된 공고를 기본 제외하므로,
    받은 모든 공고에 verdict를 저장해야 다음 세션에서 재처리되지 않는다.
    """
```

### 5. `main.py` — 툴 등록

`save_job_evaluations` 툴을 FastMCP에 등록.

## Claude 워크플로우

```
1. get_job_candidates(skills=[...])
   → job_evaluations에 없는 공고만 반환 (job_id 포함)

2. Claude가 공고 읽고 2차 추론 → 추천 목록 사용자에게 제시

3. Claude가 save_job_evaluations 자동 호출
   → 받은 모든 공고 verdict 저장
     추천한 것: "good" / 그 외: "pass"

4. 다음 세션: 평가된 공고 제외 → 새 공고만 읽음
```

## 엣지 케이스

| 상황 | 처리 |
|------|------|
| 미평가 공고 0개 | `"새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."` |
| good 공고 다시 보고 싶을 때 | `get_job_candidates(include_evaluated=True)` |
| sync_jobs로 새 공고 유입 | 평가 없으므로 자동으로 다음 추천에 포함 |
| job_skips와 중복 | 둘 다 제외 — 기존 로직 유지 |
| verdict 재평가 | upsert로 덮어쓰기 가능 |

## 변경 파일 요약

- Create: `tools/save_job_evaluations.py`
- Modify: `db/models.py` — `JobEvaluation` + `Job.evaluation` relationship 추가
- Modify: `services/job_service.py` — `get_unapplied_job_rows` 수정, `save_job_evaluations` 추가
- Modify: `tools/get_job_candidates.py` — `job_id` 반환, `include_evaluated` 파라미터 추가
- Modify: `main.py` — 툴 등록
- Modify: `tests/test_job_service.py`, `tests/test_tools.py`
