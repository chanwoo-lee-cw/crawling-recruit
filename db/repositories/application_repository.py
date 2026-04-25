from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import Application


class ApplicationRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(Application.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            status=stmt.inserted.status,
            synced_at=stmt.inserted.synced_at,
        ))
