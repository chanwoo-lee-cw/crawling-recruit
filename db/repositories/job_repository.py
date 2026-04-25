from sqlalchemy.orm import Session
from sqlalchemy import select, update, text, tuple_
from sqlalchemy.dialects.mysql import insert
from db.models import Job, JobDetail as OrmJobDetail, JobSkip, JobEvaluation, Application


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_existing_pairs(self, source: str, platform_ids: list[int]) -> set[tuple]:
        pairs = [(source, pid) for pid in platform_ids]
        return set(self.session.execute(
            select(Job.source, Job.platform_id)
            .where(tuple_(Job.source, Job.platform_id).in_(pairs))
        ).all())

    def upsert(self, rows: list[dict]):
        stmt = insert(Job.__table__).values(rows)
        update_dict = {
            "company_name": stmt.inserted.company_name,
            "title": stmt.inserted.title,
            "location": stmt.inserted.location,
            "employment_type": stmt.inserted.employment_type,
            "annual_from": stmt.inserted.annual_from,
            "annual_to": stmt.inserted.annual_to,
            "is_active": stmt.inserted.is_active,
            "synced_at": stmt.inserted.synced_at,
            "updated_at": text(
                "IF(new.company_name <> jobs.company_name OR new.title <> jobs.title "
                "OR new.location <> jobs.location OR new.employment_type <> jobs.employment_type "
                "OR new.annual_from <> jobs.annual_from OR new.annual_to <> jobs.annual_to, "
                "NOW(), jobs.updated_at)"
            ),
        }
        return self.session.execute(stmt.on_duplicate_key_update(**update_dict))

    def deactivate_removed(self, source: str, synced_pairs: list[tuple]) -> None:
        self.session.execute(
            update(Job)
            .where(Job.source == source)
            .where(tuple_(Job.source, Job.platform_id).not_in(synced_pairs))
            .where(Job.is_active == True)
            .values(is_active=False)
        )

    def find_platform_id_map(self, source: str, platform_ids: list[int]) -> dict:
        rows = self.session.execute(
            select(Job.platform_id, Job.internal_id)
            .where(Job.source == source)
            .where(Job.platform_id.in_(platform_ids))
        ).all()
        return {row.platform_id: row.internal_id for row in rows}

    def find_without_details(self, source: str, limit: int | None = None) -> list[int]:
        stmt = (
            select(Job.internal_id)
            .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
            .where(OrmJobDetail.job_id.is_(None))
            .where(Job.is_active.is_(True))
            .where(Job.source == source)
            .order_by(Job.internal_id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def find_unapplied(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> list:
        applied_pairs = (
            select(Job.company_name, Job.title)
            .join(Application, Job.internal_id == Application.job_id)
        )
        stmt = (
            select(
                Job.internal_id, Job.source, Job.platform_id,
                Job.company_name, Job.title, Job.location, Job.employment_type,
            )
            .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
            .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
            .where(JobSkip.job_id.is_(None))
            .where(Job.is_active.is_(True))
        )
        if job_group_id is not None:
            stmt = stmt.where(Job.job_group_id == job_group_id)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)
        stmt = stmt.limit(limit)
        return self.session.execute(stmt).mappings().all()

    def find_unapplied_with_details(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        include_evaluated: bool = False,
    ) -> list:
        applied_pairs = (
            select(Job.company_name, Job.title)
            .join(Application, Job.internal_id == Application.job_id)
        )
        stmt = (
            select(
                Job.internal_id, Job.source, Job.platform_id,
                Job.company_name, Job.title, Job.location, Job.employment_type,
                OrmJobDetail.requirements, OrmJobDetail.preferred_points,
                OrmJobDetail.skill_tags, OrmJobDetail.fetched_at,
            )
            .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
            .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
            .outerjoin(JobEvaluation, Job.internal_id == JobEvaluation.job_id)
            .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
            .where(JobSkip.job_id.is_(None))
            .where(Job.is_active.is_(True))
        )
        if not include_evaluated:
            stmt = stmt.where(JobEvaluation.job_id.is_(None))
        if job_group_id is not None:
            stmt = stmt.where(Job.job_group_id == job_group_id)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)
        return self.session.execute(stmt).mappings().all()
