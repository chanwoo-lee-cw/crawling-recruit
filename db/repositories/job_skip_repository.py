from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import JobSkip


class JobSkipRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(JobSkip.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            reason=stmt.inserted.reason,
            skipped_at=stmt.inserted.skipped_at,
        ))
