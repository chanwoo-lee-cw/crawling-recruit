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
    assert row["platform_id"] == 1001
    assert row["source"] == "wanted"
    assert row["company_name"] == "테스트컴퍼니"
    assert row["title"] == "Backend Engineer"
    assert row["location"] == "서울"
    assert row["employment_type"] == "regular"
    assert row["job_group_id"] == 518
    assert row["category_tag_id"] == 872
    assert row["is_active"] is True



def test_upsert_jobs_calls_execute():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        upsert_result = MagicMock()
        upsert_result.rowcount = 1
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": []}),  # existing_pairs
            upsert_result,                           # upsert
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_session.execute.called
    assert "동기화 완료: 신규 1개" in result


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
            {"internal_id": 1001, "source": "wanted", "platform_id": 1001,
             "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result
    assert "| 1001 |" in result


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
                "internal_id": 1001, "source": "wanted", "platform_id": 1001,
                "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert rows[0].internal_id == 1001
    assert rows[0].fetched_at is None


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
            internal_id=1, source="wanted", platform_id=1001,
            company_name="A사", title="Backend",
            location="서울", employment_type="regular",
            requirements="Python req", preferred_points="AWS 우대",
            skill_tags=[SkillTag(text="Python"), SkillTag(text="AWS")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=2, source="wanted", platform_id=1002,
            company_name="B사", title="Frontend",
            location="서울", employment_type="regular",
            requirements="React req", preferred_points=None,
            skill_tags=[SkillTag(text="React")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=3, source="wanted", platform_id=1003,
            company_name="C사", title="Fullstack",
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
    assert candidates[0].internal_id == 1
    assert candidates[1].internal_id == 2
    assert all(c.fetched_at is not None for c in candidates)


def test_job_candidate_from_row_parses_skill_tags():
    from domain import JobCandidate, SkillTag
    row = {
        "internal_id": 1, "source": "wanted", "platform_id": 1001,
        "company_name": "A사", "title": "Backend",
        "location": "서울", "employment_type": "regular",
        "requirements": "req", "preferred_points": None,
        "skill_tags": [{"tag_type_id": 1, "text": "Python"}, {"tag_type_id": 2, "text": "AWS"}],
        "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.internal_id == 1
    assert candidate.company_name == "A사"
    assert len(candidate.skill_tags) == 2
    assert candidate.skill_tags[0] == SkillTag(text="Python")
    assert candidate.skill_tags[1] == SkillTag(text="AWS")


def test_job_candidate_from_row_handles_null_skill_tags():
    from domain import JobCandidate
    row = {
        "internal_id": 2, "source": "wanted", "platform_id": 1002,
        "company_name": "B사", "title": "Frontend",
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
                "internal_id": 1001, "source": "wanted", "platform_id": 1001,
                "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].internal_id == 1001


def test_get_unapplied_jobs_with_skip_join():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"internal_id": 1001, "source": "wanted", "platform_id": 1001,
             "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_parse_remember_job():
    raw = {
        "id": 308098,
        "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "min_salary": None,
        "max_salary": None,
    }
    service = JobService(engine=MagicMock())
    row = service._parse_job(raw, source="remember")
    assert row["platform_id"] == 308098
    assert row["source"] == "remember"
    assert row["company_name"] == "(주)이스트소프트"
    assert row["location"] == "서울특별시 서초구"
    assert row["employment_type"] is None
    assert row["company_id"] is None


def test_upsert_jobs_remember_source():
    raw_remember_job = {
        "id": 308098,
        "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "qualifications": "Python 3년",
        "preferred_qualifications": "FastAPI 경험",
        "min_salary": None,
        "max_salary": None,
    }
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        upsert_result = MagicMock()
        upsert_result.rowcount = 1
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": []}),  # existing_pairs
            upsert_result,                           # upsert
            MagicMock(**{"all.return_value": []}),  # internal_id_map
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_jobs([raw_remember_job], source="remember", full_sync=False)

    assert "동기화 완료" in result


def test_parse_application_row_wanted():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        job_row = MagicMock()
        job_row.platform_id = 2001
        job_row.internal_id = 99
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": [job_row]}),  # job_id_map
            MagicMock(),                                    # upsert
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_applications([RAW_APP], source="wanted")

    assert "1건" in result


def test_upsert_applications_remember_source():
    raw_app = {
        "id": 303872,
        "title": "System Engineer",
        "organization": {"name": "(주)휴머스온"},
        "application": {
            "id": 3428290,
            "status": "applied",
            "applied_at": "2026-04-12T18:28:24.676+09:00",
        },
    }
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        job_row = MagicMock()
        job_row.platform_id = 303872
        job_row.internal_id = 77
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": [job_row]}),  # job_id_map
            MagicMock(),                                    # upsert
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_applications([raw_app], source="remember")

    assert "1건" in result


def test_upsert_applications_empty():
    service = JobService(engine=MagicMock())
    result = service.upsert_applications([])
    assert "0건" in result


def test_get_unapplied_job_rows_cross_platform_filter():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {
                "internal_id": 1001, "source": "wanted", "platform_id": 1001,
                "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].internal_id == 1001
    assert rows[0].source == "wanted"
    assert rows[0].platform_id == 1001


def test_get_unapplied_jobs_includes_internal_id():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"internal_id": 42, "source": "wanted", "platform_id": 1001,
             "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "| 42 |" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_get_unapplied_jobs_remember_url():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"internal_id": 99, "source": "remember", "platform_id": 308098,
             "company_name": "이스트소프트", "title": "백엔드 개발",
             "location": "서울 서초구", "employment_type": None}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "https://career.rememberapp.co.kr/job/308098" in result
    assert "| 99 |" in result


def test_save_preset_remember_keys():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError):
        service.save_preset("테스트", {"unknown_key": 1})

    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        service = JobService(engine=mock_engine)
        result = service.save_preset("리멤버 백엔드", {
            "source": "remember",
            "job_category_names": [{"level1": "SW개발", "level2": "백엔드"}],
            "min_experience": 2,
            "max_experience": 5,
        })
    assert "저장 완료" in result
