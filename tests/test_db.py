from unittest.mock import patch, MagicMock
from db.connection import get_engine, create_tables
from db.models import jobs_table, applications_table, search_presets_table


def test_models_defined():
    assert jobs_table is not None
    assert applications_table is not None
    assert search_presets_table is not None


def test_jobs_table_columns():
    col_names = {c.name for c in jobs_table.columns}
    assert col_names == {
        "id", "company_id", "company_name", "title", "location",
        "employment_type", "annual_from", "annual_to", "job_group_id",
        "category_tag_id", "is_active", "created_at", "synced_at", "updated_at"
    }


def test_applications_table_columns():
    col_names = {c.name for c in applications_table.columns}
    assert col_names == {"id", "job_id", "status", "apply_time", "synced_at"}


def test_search_presets_table_columns():
    col_names = {c.name for c in search_presets_table.columns}
    assert col_names == {"id", "name", "params", "created_at"}
