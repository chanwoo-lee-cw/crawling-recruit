import functools
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum

from sqlalchemy.orm import Session

_session_var: ContextVar[Session | None] = ContextVar("session", default=None)


def get_current_session() -> Session:
    session = _session_var.get()
    if session is None:
        raise RuntimeError("트랜잭션 컨텍스트 밖에서 세션에 접근했습니다.")
    return session


@contextmanager
def test_session_context(session: Session):
    token = _session_var.set(session)
    try:
        yield session
    finally:
        _session_var.reset(token)


test_session_context.__test__ = False  # prevent pytest from collecting this as a test


class Propagation(Enum):
    REQUIRED = "REQUIRED"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"


def _run_in_new_session(engine, func, args, kwargs):
    with Session(engine) as session:
        token = _session_var.set(session)
        try:
            result = func(*args, **kwargs)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            _session_var.reset(token)


def transactional(propagation: Propagation = Propagation.REQUIRED):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            current = _session_var.get()

            if propagation == Propagation.REQUIRED:
                if current is not None:
                    return func(self, *args, **kwargs)
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

            if propagation == Propagation.REQUIRES_NEW:
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

            if propagation == Propagation.NESTED:
                if current is not None:
                    with current.begin_nested():
                        return func(self, *args, **kwargs)
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

        return wrapper
    return decorator
