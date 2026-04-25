from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
from db.models.base import Base
from services.wanted.wanted_constants import WANTED


class Application(Base):
    __tablename__ = "applications"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=WANTED)
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.internal_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_app_source_platform"),)
    job: Mapped[Optional["Job"]] = relationship(back_populates="applications")
