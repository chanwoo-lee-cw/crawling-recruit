import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from services.job_service import JobService
from domain import JobCandidate, JobDetail, SkillTag


RAW_JOB = {
    "id": 1001,
    "company": {"id": 10, "name": "테스트컴퍼니"},
    "position": "Backend Engineer",
    "address": {"location": "서울"},
    "employment_type": "regular",
    "annual_from": 0,
    "annual_to": 100,
    "job_group_id": 518,
    "category_tag": {"parent_id": 518, "id": 872},
    "create_time": "2026-01-01T00:00:00",
}

RAW_APP = {
    "id": 9001,
    "job_id": 2001,
    "status": "complete",
    "apply_time": "2026-01-01T00:00:00",
}

RAW_DETAIL = JobDetail(
    job_id=1001,
    requirements="Python 3년 이상",
    preferred_points="FastAPI 경험자 우대",
    skill_tags=[{"tag_type_id": 1554, "text": "Python"}],
)


def test_parse_job_row():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_JOB)
    assert row["id"] == 1001
    assert row["company_name"] == "테스트컴퍼니"
    assert row["title"] == "Backend Engineer"
    assert row["location"] == "서울"
    assert row["employment_type"] == "regular"
    assert row["job_group_id"] == 518
    assert row["category_tag_id"] == 872
    assert row["is_active"] is True


def test_parse_application_row():
    service = JobService(engine=MagicMock())
    row = service._parse_application(RAW_APP)
    assert row["id"] == 9001
    assert row["job_id"] == 2001
    assert row["status"] == "complete"


def test_upsert_jobs_calls_execute():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.scalars.return_value.all.return_value = []  # existing_ids → empty (all new)
        upsert_result = MagicMock()
        upsert_result.rowcount = 1
        mock_session.execute.return_value = upsert_result

        service = JobService(engine=mock_engine)
        result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_session.scalars.called
    assert mock_session.execute.called
    assert "동기화 완료: 신규 1개, 변경 0개, 유지 0개" == result


def test_save_preset_invalid_key():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError, match="유효하지 않은 파라미터 키"):
        service.save_preset("테스트", {"invalid_key": 1})


def test_save_preset_valid():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        service = JobService(engine=mock_engine)
        result = service.save_preset("백엔드 신입 서울", {"job_group_id": 518, "locations": "서울"})

    assert "저장 완료" in result


def test_get_unapplied_jobs_returns_markdown():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "| 회사명 |" in result
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_upsert_job_details_calls_execute():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value = MagicMock()

        service = JobService(engine=mock_engine)
        result = service.upsert_job_details([RAW_DETAIL])

    assert mock_session.execute.called
    assert "1개 처리" in result


def test_get_unapplied_job_rows_returns_list():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {
                "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert rows[0].id == 1001          # 속성 접근
    assert rows[0].fetched_at is None  # 속성 접근


def test_get_jobs_without_details_filters_existing():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = [101]

        service = JobService(engine=mock_engine)
        result = service.get_jobs_without_details(job_ids=[101, 102, 103], limit=2)

    assert result == [102, 103]


def test_get_jobs_without_details_no_job_ids():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = [201, 202]

        service = JobService(engine=mock_engine)
        result = service.get_jobs_without_details(limit=10)

    assert result == [201, 202]


def test_get_recommended_jobs_scores_skill_tags():
    from datetime import datetime
    now = datetime.now()
    all_rows = [
        JobCandidate(
            id=1, company_name="A사", title="Backend",
            location="서울", employment_type="regular",
            requirements="Python req", preferred_points="AWS 우대",
            skill_tags=[SkillTag(text="Python"), SkillTag(text="AWS")],
            fetched_at=now,
        ),
        JobCandidate(
            id=2, company_name="B사", title="Frontend",
            location="서울", employment_type="regular",
            requirements="React req", preferred_points=None,
            skill_tags=[SkillTag(text="React")],
            fetched_at=now,
        ),
        JobCandidate(
            id=3, company_name="C사", title="Fullstack",
            location="서울", employment_type="regular",
            requirements=None, preferred_points=None,
            skill_tags=[], fetched_at=None,
        ),
    ]

    service = JobService(engine=MagicMock())
    candidates = service.get_recommended_jobs(
        skills=["Python", "AWS"],
        rows=all_rows,
        top_k=15,
    )

    assert len(candidates) == 2
    assert candidates[0].id == 1      # 속성 접근
    assert candidates[1].id == 2
    assert all(c.fetched_at is not None for c in candidates)


def test_job_candidate_from_row_parses_skill_tags():
    from domain import JobCandidate, SkillTag
    row = {
        "id": 1, "company_name": "A사", "title": "Backend",
        "location": "서울", "employment_type": "regular",
        "requirements": "req", "preferred_points": None,
        "skill_tags": [{"tag_type_id": 1, "text": "Python"}, {"tag_type_id": 2, "text": "AWS"}],
        "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.id == 1
    assert candidate.company_name == "A사"
    assert len(candidate.skill_tags) == 2
    assert candidate.skill_tags[0] == SkillTag(text="Python")
    assert candidate.skill_tags[1] == SkillTag(text="AWS")


def test_job_candidate_from_row_handles_null_skill_tags():
    from domain import JobCandidate
    row = {
        "id": 2, "company_name": "B사", "title": "Frontend",
        "location": None, "employment_type": None,
        "requirements": None, "preferred_points": None,
        "skill_tags": None, "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.skill_tags == []
    assert candidate.fetched_at is None


def test_skip_jobs_calls_execute():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value = MagicMock()

        service = JobService(engine=mock_engine)
        result = service.skip_jobs([101, 102], reason="연봉 낮음")

    assert mock_session.execute.called
    assert mock_session.commit.called
    assert "2개 공고 제외 완료" in result
    assert "연봉 낮음" in result


def test_skip_jobs_empty_list():
    service = JobService(engine=MagicMock())
    result = service.skip_jobs([])
    assert result == "제외할 공고 ID를 입력해주세요."


def test_get_unapplied_job_rows_with_skip_join():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {
                "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].id == 1001


def test_get_unapplied_jobs_with_skip_join():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result
