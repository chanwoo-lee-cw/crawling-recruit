from unittest.mock import MagicMock
from db.repositories.search_preset_repository import SearchPresetRepository
from db.repositories.job_detail_repository import JobDetailRepository
from db.repositories.application_repository import ApplicationRepository
from db.repositories.job_skip_repository import JobSkipRepository
from db.repositories.job_evaluation_repository import JobEvaluationRepository
from db.repositories.job_repository import JobRepository


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


def test_job_find_existing_pairs():
    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = [("wanted", 1001)]
    repo = JobRepository(mock_session)
    result = repo.find_existing_pairs("wanted", [1001, 1002])
    assert ("wanted", 1001) in result


def test_job_find_platform_id_map():
    mock_session = MagicMock()
    mock_row = MagicMock()
    mock_row.platform_id = 1001
    mock_row.internal_id = 42
    mock_session.execute.return_value.all.return_value = [mock_row]
    repo = JobRepository(mock_session)
    result = repo.find_platform_id_map("wanted", [1001])
    assert result == {1001: 42}


def test_job_find_without_details():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [201, 202]
    repo = JobRepository(mock_session)
    result = repo.find_without_details("wanted", limit=10)
    assert result == [201, 202]


def test_job_find_unapplied_returns_rows():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 1, "source": "wanted", "platform_id": 1001,
         "company_name": "A사", "title": "Backend", "location": "서울", "employment_type": "regular"}
    ]
    repo = JobRepository(mock_session)
    result = repo.find_unapplied()
    assert len(result) == 1


def test_job_find_unapplied_with_details_returns_rows():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = []
    repo = JobRepository(mock_session)
    result = repo.find_unapplied_with_details(include_evaluated=False)
    assert result == []
