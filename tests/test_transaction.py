import pytest
from unittest.mock import MagicMock, patch
from db.transaction import transactional, get_current_session, Propagation, test_session_context


def _make_svc():
    engine = MagicMock()

    class _Svc:
        def __init__(self):
            self.engine = engine

        @transactional()
        def write(self):
            return get_current_session()

        @transactional()
        def fail(self):
            raise ValueError("오류")

        @transactional(Propagation.REQUIRES_NEW)
        def requires_new(self):
            return get_current_session()

        @transactional(Propagation.NESTED)
        def nested(self):
            return get_current_session()

    return _Svc(), engine


def _mock_session_ctx(engine):
    """Session(engine) 컨텍스트 매니저를 mock하는 헬퍼"""
    mock_sess = MagicMock()
    patcher = patch("db.transaction.Session")
    MockSession = patcher.start()
    MockSession.return_value.__enter__ = MagicMock(return_value=mock_sess)
    MockSession.return_value.__exit__ = MagicMock(return_value=False)
    return patcher, MockSession, mock_sess


# --- get_current_session ---

def test_get_current_session_raises_outside_transaction():
    with pytest.raises(RuntimeError, match="트랜잭션 컨텍스트"):
        get_current_session()


# --- test_session_context ---

def test_test_session_context_sets_and_resets():
    mock_sess = MagicMock()
    with test_session_context(mock_sess):
        assert get_current_session() is mock_sess
    with pytest.raises(RuntimeError):
        get_current_session()


# --- REQUIRED ---

def test_required_creates_session_and_commits():
    svc, engine = _make_svc()
    patcher, MockSession, mock_sess = _mock_session_ctx(engine)
    try:
        result = svc.write()
    finally:
        patcher.stop()
    MockSession.assert_called_once_with(engine)
    mock_sess.commit.assert_called_once()
    assert result is mock_sess


def test_required_joins_existing_without_commit():
    svc, _ = _make_svc()
    mock_sess = MagicMock()
    with test_session_context(mock_sess):
        result = svc.write()
    mock_sess.commit.assert_not_called()
    assert result is mock_sess


def test_required_rolls_back_on_exception():
    svc, engine = _make_svc()
    patcher, _, mock_sess = _mock_session_ctx(engine)
    try:
        with pytest.raises(ValueError):
            svc.fail()
    finally:
        patcher.stop()
    mock_sess.rollback.assert_called_once()
    mock_sess.commit.assert_not_called()


# --- REQUIRES_NEW ---

def test_requires_new_creates_new_session_ignoring_existing():
    svc, engine = _make_svc()
    existing = MagicMock()
    patcher, MockSession, new_sess = _mock_session_ctx(engine)
    try:
        with test_session_context(existing):
            result = svc.requires_new()
    finally:
        patcher.stop()
    assert result is new_sess
    new_sess.commit.assert_called_once()
    existing.commit.assert_not_called()


# --- NESTED ---

def test_nested_uses_savepoint_with_existing_session():
    svc, _ = _make_svc()
    existing = MagicMock()
    existing.begin_nested.return_value.__enter__ = MagicMock(return_value=existing)
    existing.begin_nested.return_value.__exit__ = MagicMock(return_value=False)
    with test_session_context(existing):
        result = svc.nested()
    existing.begin_nested.assert_called_once()
    assert result is existing


def test_nested_falls_back_to_required_when_no_session():
    svc, engine = _make_svc()
    patcher, MockSession, mock_sess = _mock_session_ctx(engine)
    try:
        result = svc.nested()
    finally:
        patcher.stop()
    MockSession.assert_called_once_with(engine)
    mock_sess.commit.assert_called_once()
    assert result is mock_sess
