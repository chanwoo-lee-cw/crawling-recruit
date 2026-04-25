from unittest.mock import MagicMock
from db.repositories.search_preset_repository import SearchPresetRepository
from db.repositories.job_detail_repository import JobDetailRepository
from db.repositories.application_repository import ApplicationRepository
from db.repositories.job_skip_repository import JobSkipRepository
from db.repositories.job_evaluation_repository import JobEvaluationRepository


def test_find_by_name_returns_none_when_missing():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None
    repo = SearchPresetRepository(mock_session)
    assert repo.find_by_name("없는이름") is None


def test_find_all_returns_list():
    mock_session = MagicMock()
    mock_preset = MagicMock()
    mock_preset.name = "테스트"
    mock_session.scalars.return_value.all.return_value = [mock_preset]
    repo = SearchPresetRepository(mock_session)
    result = repo.find_all()
    assert len(result) == 1
    assert result[0].name == "테스트"


def test_upsert_calls_execute():
    mock_session = MagicMock()
    repo = SearchPresetRepository(mock_session)
    repo.upsert({"name": "x", "params": {}, "created_at": None})
    assert mock_session.execute.called


def test_job_detail_find_existing_job_ids():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [101, 102]
    repo = JobDetailRepository(mock_session)
    result = repo.find_existing_job_ids([101, 102, 103])
    assert result == {101, 102}


def test_job_detail_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobDetailRepository(mock_session)
    repo.upsert([{"job_id": 1, "requirements": "Python", "preferred_points": None,
                  "skill_tags": [], "fetched_at": None}])
    assert mock_session.execute.called


def test_application_upsert_calls_execute():
    mock_session = MagicMock()
    repo = ApplicationRepository(mock_session)
    repo.upsert([{"source": "wanted", "platform_id": 1, "job_id": 1,
                  "status": "complete", "apply_time": None, "synced_at": None}])
    assert mock_session.execute.called


def test_job_skip_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobSkipRepository(mock_session)
    repo.upsert([{"job_id": 1, "reason": "연봉 낮음", "skipped_at": None}])
    assert mock_session.execute.called


def test_job_evaluation_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobEvaluationRepository(mock_session)
    repo.upsert([{"job_id": 1, "verdict": "good", "evaluated_at": None}])
    assert mock_session.execute.called
