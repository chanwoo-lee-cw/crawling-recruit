from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from db.models.base import Base


class JobSkip(Base):
    __tablename__ = "job_skips"
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    skipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    job: Mapped["Job"] = relationship(back_populates="skip")
