from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, DateTime, UniqueConstraint
from db.models.base import Base
from services.wanted.wanted_constants import WANTED


class Job(Base):
    __tablename__ = "jobs"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=WANTED)
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(Integer)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(100))
    employment_type: Mapped[Optional[str]] = mapped_column(String(50))
    annual_from: Mapped[Optional[int]] = mapped_column(Integer)
    annual_to: Mapped[Optional[int]] = mapped_column(Integer)
    job_group_id: Mapped[Optional[int]] = mapped_column(Integer)
    category_tag_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_source_platform"),)
    detail: Mapped[Optional["JobDetail"]] = relationship(back_populates="job", uselist=False)
    applications: Mapped[List["Application"]] = relationship(back_populates="job")
    skip: Mapped[Optional["JobSkip"]] = relationship(back_populates="job", uselist=False)
    evaluation: Mapped[Optional["JobEvaluation"]] = relationship(back_populates="job", uselist=False)
