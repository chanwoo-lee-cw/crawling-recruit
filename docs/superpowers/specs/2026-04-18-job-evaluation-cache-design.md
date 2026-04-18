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

```python
class JobEvaluation(Base):
    __tablename__ = "job_evaluations"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

### 2. `services/job_service.py`

**`get_unapplied_job_rows` 수정**: 쿼리에 `LEFT JOIN job_evaluations` 추가, `job_evaluations.job_id IS NULL`인 공고만 반환.

`include_evaluated: bool = False` 파라미터 추가 — `True`이면 평가된 공고도 포함.

**`save_job_evaluations` 메서드 추가**:

```python
def save_job_evaluations(self, evaluations: list[dict]) -> str:
    # evaluations: [{"job_id": int, "verdict": str}, ...]
    # verdict가 "good"/"pass"/"skip"이 아닌 경우 ValueError
    # on_duplicate_key_update로 upsert (재평가 가능)
```

### 3. `tools/save_job_evaluations.py` — 새 MCP 툴

```python
def save_job_evaluations(evaluations: list[dict]) -> str:
    """Claude가 평가한 공고 verdict를 저장한다.

    evaluations: [{"job_id": int, "verdict": "good"|"pass"|"skip"}, ...]
    - good: 지원 고려 대상
    - pass: 이번엔 해당 없음
    - skip: 영구 제외
    get_job_candidates는 이미 평가된 공고를 기본 제외하므로,
    받은 모든 공고에 verdict를 저장해야 다음 세션에서 재처리되지 않는다.
    """
```

### 4. `main.py` — 툴 등록

`save_job_evaluations` 툴을 FastMCP에 등록.

## Claude 워크플로우

```
1. get_job_candidates(skills=[...])
   → job_evaluations에 없는 공고만 반환

2. Claude가 공고 읽고 2차 추론 → 추천 목록 사용자에게 제시

3. Claude가 save_job_evaluations 자동 호출
   → 이번에 받은 모든 공고 verdict 저장
     추천한 것: "good" / 그 외: "pass"

4. 다음 세션: 평가된 공고 제외 → 새 공고만 읽음
```

## 엣지 케이스

| 상황 | 처리 |
|------|------|
| 미평가 공고 0개 | `"새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."` |
| good 공고 다시 보고 싶을 때 | `get_job_candidates(include_evaluated=True)` 파라미터로 포함 |
| sync_jobs로 새 공고 유입 | 평가 없으므로 자동으로 다음 추천에 포함 |
| job_skips와 중복 | 둘 다 제외 — 기존 로직 유지 |
| verdict 재평가 | upsert로 덮어쓰기 가능 |

## 변경 파일 요약

- Create: `tools/save_job_evaluations.py`
- Modify: `db/models.py` — `JobEvaluation` 추가
- Modify: `services/job_service.py` — `get_unapplied_job_rows`, `save_job_evaluations` 추가
- Modify: `main.py` — 툴 등록
- Modify: `tests/test_job_service.py`, `tests/test_tools.py`
