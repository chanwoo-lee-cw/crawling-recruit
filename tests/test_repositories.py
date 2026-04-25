from unittest.mock import MagicMock
from db.repositories.search_preset_repository import SearchPresetRepository


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
