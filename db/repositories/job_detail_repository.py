from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from db.models import JobDetail as OrmJobDetail


class JobDetailRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_existing_job_ids(self, job_ids: list[int]) -> set[int]:
        return set(self.session.scalars(
            select(OrmJobDetail.job_id).where(OrmJobDetail.job_id.in_(job_ids))
        ).all())

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(OrmJobDetail.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            requirements=stmt.inserted.requirements,
            preferred_points=stmt.inserted.preferred_points,
            skill_tags=stmt.inserted.skill_tags,
            fetched_at=stmt.inserted.fetched_at,
        ))
