from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import JobEvaluation


class JobEvaluationRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(JobEvaluation.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            verdict=stmt.inserted.verdict,
            evaluated_at=stmt.inserted.evaluated_at,
        ))
