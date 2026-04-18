from db.models import Job, Application, JobDetail, SearchPreset, JobSkip


def test_models_defined():
    assert Job.__table__ is not None
    assert Application.__table__ is not None
    assert JobDetail.__table__ is not None
    assert SearchPreset.__table__ is not None
    assert JobSkip.__table__ is not None


def test_jobs_table_columns():
    col_names = {c.name for c in Job.__table__.columns}
    assert col_names == {
        "internal_id", "source", "platform_id",
        "company_id", "company_name", "title", "location",
        "employment_type", "annual_from", "annual_to", "job_group_id",
        "category_tag_id", "is_active", "created_at", "synced_at", "updated_at"
    }


def test_applications_table_columns():
    col_names = {c.name for c in Application.__table__.columns}
    assert col_names == {"internal_id", "source", "platform_id", "job_id", "status", "apply_time", "synced_at"}


def test_job_details_table_columns():
    col_names = {c.name for c in JobDetail.__table__.columns}
    assert col_names == {"job_id", "requirements", "preferred_points", "skill_tags", "fetched_at"}


def test_search_presets_table_columns():
    col_names = {c.name for c in SearchPreset.__table__.columns}
    assert col_names == {"id", "name", "params", "created_at"}


def test_job_skips_table_columns():
    col_names = {c.name for c in JobSkip.__table__.columns}
    assert col_names == {"job_id", "reason", "skipped_at"}


def test_job_evaluation_model_columns():
    from db.models import JobEvaluation
    cols = {c.name for c in JobEvaluation.__table__.columns}
    assert cols == {"job_id", "verdict", "evaluated_at"}


def test_job_model_has_evaluation_relationship():
    from db.models import Job
    assert hasattr(Job, "evaluation")
