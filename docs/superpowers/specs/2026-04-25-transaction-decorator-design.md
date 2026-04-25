# 트랜잭션 데코레이터 설계 스펙

## 배경

`JobService`의 각 메서드마다 `with Session(self.engine) as session: ... session.commit()` 패턴이 반복되어 트랜잭션 관리가 분산되어 있다. 이를 데코레이터로 중앙화하여 관리 포인트를 단일화한다.

## 목표

- 트랜잭션 생명주기(생성, 커밋, 롤백)를 데코레이터로 분리
- Spring의 `@Transactional(propagation = ...)` 방식으로 중첩 트랜잭션 제어
- 메서드 시그니처 변경 없이 `get_current_session()`으로 세션 접근 (ContextVar 투명 주입)
- 기존 `tools/` 등 호출부 변경 없음

## 구성 요소

### 1. `db/transaction.py` (신규)

```python
from contextvars import ContextVar
from enum import Enum
from sqlalchemy.orm import Session

_session_var: ContextVar[Session | None] = ContextVar('session', default=None)

def get_current_session() -> Session:
    session = _session_var.get()
    if session is None:
        raise RuntimeError("트랜잭션 컨텍스트 밖에서 세션에 접근했습니다.")
    return session

class Propagation(Enum):
    REQUIRED = "REQUIRED"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"

def transactional(propagation: Propagation = Propagation.REQUIRED):
    def decorator(func): ...
    return decorator
```

### 2. `services/jobs/job_service.py` (수정)

각 write 메서드에 `@transactional()` 적용, 내부 `Session(self.engine)` 블록 및 `session.commit()` 제거.

## Propagation 동작

| 모드 | 기존 세션 있음 | 기존 세션 없음 |
|---|---|---|
| REQUIRED (기본) | 기존 세션 합류, 커밋 안 함 | 새 세션 생성, 끝에 commit |
| REQUIRES_NEW | 새 세션 독립 생성, 독립 commit | 새 세션 생성, 끝에 commit |
| NESTED | begin_nested() (savepoint) | REQUIRED fallback |

예외 발생 시: REQUIRED/REQUIRES_NEW → rollback 후 re-raise. NESTED → savepoint만 롤백, 외부 트랜잭션 유지. NESTED에서 외부 세션이 없을 때 fallback 시에도 에러 처리는 REQUIRED와 동일하게 rollback 후 re-raise.

> **Note:** `REQUIRES_NEW`는 현재 코드베이스에서 사용하지 않지만, 향후 감사 로그 등 독립 트랜잭션이 필요한 경우를 위해 포함한다.

## upsert_jobs 중간 커밋 제거

기존에 `upsert` 후 `commit()`, `deactivate_removed` 후 `commit()` 두 번 호출하던 것을 하나의 트랜잭션으로 합친다. 두 커밋은 순서 보장 목적이었을 뿐 기술적 필수 조건이 아니다. SQLAlchemy의 identity map이 동일 세션 내 쓰기 가시성을 보장하며, DB 레벨 트리거는 존재하지 않는다.

## 테스트 전략

`db/transaction.py`에 테스트용 컨텍스트 매니저 `test_session_context(session)`을 공개 API로 제공한다. 내부 `_session_var`을 직접 노출하지 않아 리팩토링 시 테스트가 깨지는 것을 방지한다.

```python
# db/transaction.py에 추가
from contextlib import contextmanager

@contextmanager
def test_session_context(session):
    token = _session_var.set(session)
    try:
        yield session
    finally:
        _session_var.reset(token)

# 테스트에서 사용
from db.transaction import test_session_context

with Session(engine) as session:
    with test_session_context(session):
        service.upsert_jobs(raw_jobs)
    session.rollback()
```

## 변경 파일

| 파일 | 변경 |
|---|---|
| `db/transaction.py` | 신규 생성 |
| `services/jobs/job_service.py` | @transactional 적용, 세션 관리 코드 제거 |
| `tests/test_job_service.py` | ContextVar 기반 세션 주입으로 수정 |

## 변경 없는 파일

- `tools/` 하위 모든 파일 (호출부 시그니처 변경 없음)
- `db/repositories/` (세션을 생성자로 받는 구조 유지)
- `db/connection.py`
