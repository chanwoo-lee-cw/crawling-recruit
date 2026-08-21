from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, update, bindparam
from sqlalchemy.dialects.mysql import insert
from db.models import JobDetail as OrmJobDetail, Job


class JobDetailRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_existing_job_ids(self, job_ids: list[int]) -> set[int]:
        return set(self.session.scalars(
            select(OrmJobDetail.job_id).where(OrmJobDetail.job_id.in_(job_ids))
        ).all())

    def find_for_backfill(self, days: int | None = None, source: str | None = None) -> list[dict]:
        """태그 백필 대상 상세 조회. days 지정 시 최근 N일 내 목록에서 관측된 공고만."""
        stmt = (
            select(
                OrmJobDetail.job_id, OrmJobDetail.requirements,
                OrmJobDetail.preferred_points, OrmJobDetail.skill_tags,
            )
            .join(Job, Job.internal_id == OrmJobDetail.job_id)
            .where(OrmJobDetail.fetched_at.is_not(None))
            .where(Job.is_active.is_(True))
        )
        if days is not None:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            stmt = stmt.where(Job.synced_at >= cutoff)
        if source:
            stmt = stmt.where(Job.source == source)
        return [dict(r) for r in self.session.execute(stmt).mappings().all()]

    def update_skill_tags(self, rows: list[dict]) -> None:
        """skill_tags만 갱신한다. fetched_at은 상세 재수집 대상 판단에 쓰이므로 건드리지 않는다."""
        if not rows:
            return
        stmt = (
            update(OrmJobDetail.__table__)
            .where(OrmJobDetail.job_id == bindparam("b_job_id"))
            .values(skill_tags=bindparam("skill_tags"))
        )
        self.session.execute(
            stmt,
            [{"b_job_id": r["job_id"], "skill_tags": r["skill_tags"]} for r in rows],
        )

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(OrmJobDetail.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            requirements=stmt.inserted.requirements,
            preferred_points=stmt.inserted.preferred_points,
            skill_tags=stmt.inserted.skill_tags,
            fetched_at=stmt.inserted.fetched_at,
        ))
