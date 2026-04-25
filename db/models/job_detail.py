from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, DateTime, Text, JSON, ForeignKey
from db.models.base import Base


class JobDetail(Base):
    __tablename__ = "job_details"
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    requirements: Mapped[Optional[str]] = mapped_column(Text)
    preferred_points: Mapped[Optional[str]] = mapped_column(Text)
    skill_tags: Mapped[Optional[list]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    job: Mapped["Job"] = relationship(back_populates="detail")
