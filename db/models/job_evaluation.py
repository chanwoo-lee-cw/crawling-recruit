from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from db.models.base import Base


class JobEvaluation(Base):
    __tablename__ = "job_evaluations"
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    job: Mapped["Job"] = relationship(back_populates="evaluation")
