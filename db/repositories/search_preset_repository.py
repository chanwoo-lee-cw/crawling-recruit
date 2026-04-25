from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from db.models import SearchPreset


class SearchPresetRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, row: dict) -> None:
        stmt = insert(SearchPreset.__table__).values([row])
        self.session.execute(stmt.on_duplicate_key_update(
            params=stmt.inserted.params,
            created_at=stmt.inserted.created_at,
        ))

    def find_all(self) -> list[SearchPreset]:
        return list(self.session.scalars(
            select(SearchPreset).order_by(SearchPreset.created_at)
        ).all())

    def find_by_name(self, name: str) -> SearchPreset | None:
        return self.session.scalars(
            select(SearchPreset).where(SearchPreset.name == name)
        ).first()
