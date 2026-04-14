from sqlalchemy import (
    Table, Column, Integer, String, Boolean, DateTime, JSON, MetaData, Text, ForeignKey
)

metadata = MetaData()

jobs_table = Table(
    "jobs", metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False),
    Column("company_name", String(255), nullable=False),
    Column("title", String(255), nullable=False),
    Column("location", String(100)),
    Column("employment_type", String(50)),
    Column("annual_from", Integer),
    Column("annual_to", Integer),
    Column("job_group_id", Integer),
    Column("category_tag_id", Integer),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime),
    Column("synced_at", DateTime, nullable=False),
    Column("updated_at", DateTime),
)

applications_table = Table(
    "applications", metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", Integer, nullable=False),
    Column("status", String(50), nullable=False),
    Column("apply_time", DateTime),
    Column("synced_at", DateTime, nullable=False),
)

search_presets_table = Table(
    "search_presets", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column("params", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

job_details_table = Table(
    "job_details", metadata,
    Column("job_id", Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column("requirements", Text),
    Column("preferred_points", Text),
    Column("skill_tags", JSON),
    Column("fetched_at", DateTime, nullable=False),
)
