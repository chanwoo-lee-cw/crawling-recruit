from unittest.mock import MagicMock, patch

from db.repositories.job_detail_repository import JobDetailRepository
from db.transaction import test_session_context
from services.jobs.job_service import JobService


def _row(job_id, requirements, preferred_points=None, skill_tags=None):
    return {
        "job_id": job_id,
        "requirements": requirements,
        "preferred_points": preferred_points,
        "skill_tags": skill_tags if skill_tags is not None else [],
    }


def test_backfill_returns_message_when_no_keywords():
    service = JobService(engine=MagicMock())
    with patch.object(JobService, "list_keywords", return_value=[]), \
         test_session_context(MagicMock()):
        result = service.backfill_skill_tags()
    assert "키워드" in result


def test_backfill_adds_matching_tags():
    service = JobService(engine=MagicMock())
    rows = [
        _row(1, "Java, Spring Boot 경험자", "Kafka 우대"),
        _row(2, "React 프론트엔드"),
    ]
    with patch.object(JobService, "list_keywords", return_value=["Java", "Spring Boot", "Kafka"]), \
         patch.object(JobDetailRepository, "find_for_backfill", return_value=rows), \
         patch.object(JobDetailRepository, "update_skill_tags") as mock_update, \
         test_session_context(MagicMock()):
        result = service.backfill_skill_tags(days=30)

    saved = mock_update.call_args[0][0]
    assert len(saved) == 1
    assert saved[0]["job_id"] == 1
    assert {t["text"] for t in saved[0]["skill_tags"]} == {"Java", "Spring Boot", "Kafka"}
    assert "2건" in result and "1건" in result


def test_backfill_is_idempotent_for_existing_tags():
    service = JobService(engine=MagicMock())
    rows = [_row(1, "Java 경험자", None, [{"text": "Java"}])]
    with patch.object(JobService, "list_keywords", return_value=["Java"]), \
         patch.object(JobDetailRepository, "find_for_backfill", return_value=rows), \
         patch.object(JobDetailRepository, "update_skill_tags") as mock_update, \
         test_session_context(MagicMock()):
        service.backfill_skill_tags()

    assert not mock_update.called


def test_backfill_passes_days_and_source_to_repository():
    service = JobService(engine=MagicMock())
    with patch.object(JobService, "list_keywords", return_value=["Java"]), \
         patch.object(JobDetailRepository, "find_for_backfill", return_value=[]) as mock_find, \
         test_session_context(MagicMock()):
        service.backfill_skill_tags(days=7, source="wanted")

    assert mock_find.call_args.kwargs == {"days": 7, "source": "wanted"}


def test_update_skill_tags_only_touches_tag_column():
    """fetched_at을 건드리면 상세 재수집 대상 판단이 깨진다."""
    mock_session = MagicMock()
    JobDetailRepository(mock_session).update_skill_tags(
        [{"job_id": 1, "skill_tags": [{"text": "Java"}]}]
    )
    sql = str(mock_session.execute.call_args[0][0])
    assert "fetched_at" not in sql
    assert "skill_tags" in sql
