import json
from datetime import datetime, timezone
from sqlalchemy import select, update, text, tuple_
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from db.models import Job, Application, JobDetail as OrmJobDetail, SearchPreset, JobSkip, JobEvaluation
from domain import JobCandidate, JobDetail

ALLOWED_PRESET_KEYS = {
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    "job_category_names", "min_experience", "max_experience", "source",
}
WANTED_JOB_BASE_URL = "https://www.wanted.co.kr/wd"
REMEMBER_JOB_BASE_URL = "https://career.rememberapp.co.kr/job/posting"

JOB_BASE_URLS = {
    "wanted": WANTED_JOB_BASE_URL,
    "remember": REMEMBER_JOB_BASE_URL,
}


class JobService:
    EMPLOYMENT_TYPE_MAP = {
        "정규직": "regular",
        "인턴": "intern",
        "계약직": "contract",
    }
    VALID_VERDICTS = {"good", "pass", "skip"}

    def __init__(self, engine):
        self.engine = engine

    def _parse_wanted_job(self, raw: dict) -> dict:
        address = raw.get("address") or {}
        location_str = address.get("location", "")
        district = address.get("district", "")
        location = f"{location_str} {district}".strip() if district else location_str

        category_tag = raw.get("category_tag") or {}
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        create_time = raw.get("create_time")
        created_at = datetime.fromisoformat(create_time) if create_time else None

        return {
            "source": "wanted",
            "platform_id": raw["id"],
            "company_id": raw["company"]["id"],
            "company_name": raw["company"]["name"],
            "title": raw["position"],
            "location": location,
            "employment_type": raw.get("employment_type"),
            "annual_from": raw.get("annual_from"),
            "annual_to": raw.get("annual_to"),
            "job_group_id": raw.get("job_group_id"),
            "category_tag_id": category_tag.get("id"),
            "is_active": True,
            "created_at": created_at,
            "synced_at": now,
            "updated_at": None,
        }

    def _parse_remember_job(self, raw: dict) -> dict:
        addresses = raw.get("addresses") or []
        if addresses:
            addr = addresses[0]
            parts = [addr.get("address_level1", ""), addr.get("address_level2", "")]
            location = " ".join(p for p in parts if p).strip() or None
        else:
            location = None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return {
            "source": "remember",
            "platform_id": raw["id"],
            "company_id": raw["organization"].get("company_id"),
            "company_name": raw["organization"]["name"],
            "title": raw["title"],
            "location": location,
            "employment_type": None,
            "annual_from": raw.get("min_salary"),
            "annual_to": raw.get("max_salary"),
            "job_group_id": None,
            "category_tag_id": None,
            "is_active": True,
            "created_at": None,
            "synced_at": now,
            "updated_at": None,
        }

    def _parse_job(self, raw: dict, source: str = "wanted") -> dict:
        if source == "remember":
            return self._parse_remember_job(raw)
        return self._parse_wanted_job(raw)

    def _parse_application(self, raw: dict) -> dict:
        apply_time = raw.get("apply_time")
        return {
            "id": raw["id"],
            "job_id": raw["job_id"],
            "status": raw["status"],
            "apply_time": datetime.fromisoformat(apply_time) if apply_time else None,
            "synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    def upsert_jobs(self, raw_jobs: list[dict], source: str = "wanted", full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

        rows = [self._parse_job(j, source=source) for j in raw_jobs]
        synced_pairs = [(source, r["platform_id"]) for r in rows]

        with Session(self.engine) as session:
            existing_pairs = set(session.execute(
                select(Job.source, Job.platform_id)
                .where(tuple_(Job.source, Job.platform_id).in_(synced_pairs))
            ).all())
            new_count = len(rows) - len(existing_pairs)

            stmt = insert(Job.__table__).values(rows)
            update_dict = {
                "company_name": stmt.inserted.company_name,
                "title": stmt.inserted.title,
                "location": stmt.inserted.location,
                "employment_type": stmt.inserted.employment_type,
                "annual_from": stmt.inserted.annual_from,
                "annual_to": stmt.inserted.annual_to,
                "is_active": stmt.inserted.is_active,
                "synced_at": stmt.inserted.synced_at,
                "updated_at": text(
                    "IF(new.company_name <> jobs.company_name OR new.title <> jobs.title "
                    "OR new.location <> jobs.location OR new.employment_type <> jobs.employment_type "
                    "OR new.annual_from <> jobs.annual_from OR new.annual_to <> jobs.annual_to, "
                    "NOW(), jobs.updated_at)"
                ),
            }
            upsert_stmt = stmt.on_duplicate_key_update(**update_dict)
            result = session.execute(upsert_stmt)
            session.commit()

            if full_sync and synced_pairs:
                session.execute(
                    update(Job)
                    .where(Job.source == source)
                    .where(tuple_(Job.source, Job.platform_id).not_in(synced_pairs))
                    .where(Job.is_active == True)
                    .values(is_active=False)
                )
                session.commit()

            if source == "remember":
                platform_ids = [r["platform_id"] for r in rows]
                internal_id_map = {row.platform_id: row.internal_id for row in session.execute(
                    select(Job.platform_id, Job.internal_id)
                    .where(Job.source == "remember")
                    .where(Job.platform_id.in_(platform_ids))
                ).all()}
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                detail_rows = []
                for raw_job in raw_jobs:
                    internal_id = internal_id_map.get(raw_job["id"])
                    if internal_id:
                        categories = raw_job.get("job_categories") or []
                        skill_tags = [{"text": c["level2"]} for c in categories if c.get("level2")]
                        detail_rows.append({
                            "job_id": internal_id,
                            "requirements": raw_job.get("qualifications"),
                            "preferred_points": raw_job.get("preferred_qualifications"),
                            "skill_tags": skill_tags,
                            "fetched_at": now,
                        })
                if detail_rows:
                    detail_stmt = insert(OrmJobDetail.__table__).values(detail_rows)
                    detail_upsert = detail_stmt.on_duplicate_key_update(
                        requirements=detail_stmt.inserted.requirements,
                        preferred_points=detail_stmt.inserted.preferred_points,
                        skill_tags=detail_stmt.inserted.skill_tags,
                        fetched_at=detail_stmt.inserted.fetched_at,
                    )
                    session.execute(detail_upsert)
                    session.commit()

            updated_count = (result.rowcount - new_count) // 2
            unchanged_count = len(rows) - new_count - updated_count
            return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"

    def upsert_applications(self, raw_apps: list[dict], source: str = "wanted") -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        with Session(self.engine) as session:
            if source == "wanted":
                job_platform_ids = [app["job_id"] for app in raw_apps]
            else:
                job_platform_ids = [app["id"] for app in raw_apps]

            job_id_map = {row.platform_id: row.internal_id for row in session.execute(
                select(Job.platform_id, Job.internal_id)
                .where(Job.source == source)
                .where(Job.platform_id.in_(job_platform_ids))
            ).all()}

            rows = []
            for app in raw_apps:
                if source == "wanted":
                    job_platform_id = app["job_id"]
                    platform_id = app["id"]
                    status = app["status"]
                    apply_time_str = app.get("apply_time")
                else:
                    job_platform_id = app["id"]
                    application = app.get("application")
                    if not application:
                        continue
                    platform_id = application["id"]
                    status = application["status"]
                    apply_time_str = application.get("applied_at")

                job_internal_id = job_id_map.get(job_platform_id)
                if job_internal_id is None:
                    continue

                apply_time = datetime.fromisoformat(apply_time_str).replace(tzinfo=None) if apply_time_str else None
                rows.append({
                    "source": source,
                    "platform_id": platform_id,
                    "job_id": job_internal_id,
                    "status": status,
                    "apply_time": apply_time,
                    "synced_at": now,
                })

            if not rows:
                return "지원현황 동기화 완료: 총 0건"

            stmt = insert(Application.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                status=stmt.inserted.status,
                synced_at=stmt.inserted.synced_at,
            )
            session.execute(upsert_stmt)
            session.commit()

        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    def upsert_job_details(self, details: list[JobDetail]) -> str:
        if not details:
            return "완료: 0개 처리"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {
                "job_id": d.job_id,
                "requirements": d.requirements,
                "preferred_points": d.preferred_points,
                "skill_tags": d.skill_tags,
                "fetched_at": now,
            }
            for d in details
        ]
        with Session(self.engine) as session:
            stmt = insert(OrmJobDetail.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                requirements=stmt.inserted.requirements,
                preferred_points=stmt.inserted.preferred_points,
                skill_tags=stmt.inserted.skill_tags,
                fetched_at=stmt.inserted.fetched_at,
            )
            session.execute(upsert_stmt)
            session.commit()
        return f"완료: {len(rows)}개 처리"

    def get_jobs_without_details(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[int]:
        if job_ids is not None:
            with Session(self.engine) as session:
                existing = set(session.scalars(
                    select(OrmJobDetail.job_id).where(OrmJobDetail.job_id.in_(job_ids))
                ).all())
            missing = [jid for jid in job_ids if jid not in existing]
            return missing[:limit] if limit is not None else missing

        stmt = (
            select(Job.internal_id)
            .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
            .where(OrmJobDetail.job_id.is_(None))
            .where(Job.is_active.is_(True))
            .where(Job.source == "wanted")
            .order_by(Job.internal_id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        with Session(self.engine) as session:
            return list(session.scalars(stmt).all())

    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)

        applied_pairs = (
            select(Job.company_name, Job.title)
            .join(Application, Job.internal_id == Application.job_id)
        )

        stmt = (
            select(
                Job.internal_id, Job.source, Job.platform_id,
                Job.company_name, Job.title, Job.location, Job.employment_type,
            )
            .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
            .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
            .where(JobSkip.job_id.is_(None))
            .where(Job.is_active.is_(True))
        )

        if job_group_id is not None:
            stmt = stmt.where(Job.job_group_id == job_group_id)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)
        stmt = stmt.limit(limit)

        with Session(self.engine) as session:
            rows = session.execute(stmt).mappings().all()

        if not rows:
            return "미지원 공고가 없습니다."

        lines = ["| internal_id | 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|---|"]
        for row in rows:
            base_url = JOB_BASE_URLS.get(row["source"], WANTED_JOB_BASE_URL)
            link = f"{base_url}/{row['platform_id']}"
            lines.append(
                f"| {row['internal_id']} | {row['company_name']} | {row['title']} | {row['location']} | {link} |"
            )
        lines.append(f"총 {len(rows)}개의 미지원 공고")
        return "\n".join(lines)

    def get_unapplied_job_rows(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        include_evaluated: bool = False,
    ) -> list[JobCandidate]:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)

        applied_pairs = (
            select(Job.company_name, Job.title)
            .join(Application, Job.internal_id == Application.job_id)
        )

        stmt = (
            select(
                Job.internal_id, Job.source, Job.platform_id,
                Job.company_name, Job.title, Job.location, Job.employment_type,
                OrmJobDetail.requirements, OrmJobDetail.preferred_points,
                OrmJobDetail.skill_tags, OrmJobDetail.fetched_at,
            )
            .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
            .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
            .outerjoin(JobEvaluation, Job.internal_id == JobEvaluation.job_id)
            .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
            .where(JobSkip.job_id.is_(None))
            .where(Job.is_active.is_(True))
        )

        if not include_evaluated:
            stmt = stmt.where(JobEvaluation.job_id.is_(None))

        if job_group_id is not None:
            stmt = stmt.where(Job.job_group_id == job_group_id)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)

        with Session(self.engine) as session:
            rows = session.execute(stmt).mappings().all()

        return [JobCandidate.from_row(r) for r in rows]

    def skip_jobs(self, job_ids: list[int], reason: str | None = None) -> str:
        if not job_ids:
            return "제외할 공고 ID를 입력해주세요."
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [{"job_id": jid, "reason": reason, "skipped_at": now} for jid in job_ids]
        with Session(self.engine) as session:
            stmt = insert(JobSkip.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                reason=stmt.inserted.reason,
                skipped_at=stmt.inserted.skipped_at,
            )
            session.execute(upsert_stmt)
            session.commit()
        suffix = f" (사유: {reason})" if reason else ""
        return f"{len(job_ids)}개 공고 제외 완료{suffix}"

    def save_job_evaluations(self, evaluations: list[dict]) -> str:
        if not evaluations:
            return "0개 처리"
        invalid = [e["verdict"] for e in evaluations if e.get("verdict") not in self.VALID_VERDICTS]
        if invalid:
            raise ValueError(
                f"유효하지 않은 verdict: {invalid}. 허용 값: good, pass, skip"
            )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {"job_id": e["job_id"], "verdict": e["verdict"], "evaluated_at": now}
            for e in evaluations
        ]
        with Session(self.engine) as session:
            stmt = insert(JobEvaluation.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                verdict=stmt.inserted.verdict,
                evaluated_at=stmt.inserted.evaluated_at,
            )
            session.execute(upsert_stmt)
            session.commit()
        return f"{len(rows)}개 평가 저장 완료"

    def save_preset(self, name: str, params: dict) -> str:
        invalid_keys = set(params.keys()) - ALLOWED_PRESET_KEYS
        if invalid_keys:
            raise ValueError(
                f"유효하지 않은 파라미터 키: {sorted(invalid_keys)}. "
                f"허용 키: {', '.join(sorted(ALLOWED_PRESET_KEYS))}"
            )

        row = {
            "name": name,
            "params": params,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        with Session(self.engine) as session:
            stmt = insert(SearchPreset.__table__).values([row])
            upsert_stmt = stmt.on_duplicate_key_update(
                params=stmt.inserted.params,
                created_at=stmt.inserted.created_at,
            )
            session.execute(upsert_stmt)
            session.commit()

        return f"프리셋 '{name}' 저장 완료"

    def list_presets(self) -> str:
        with Session(self.engine) as session:
            presets = session.scalars(
                select(SearchPreset).order_by(SearchPreset.created_at)
            ).all()

        if not presets:
            return "저장된 프리셋이 없습니다."
        names = ", ".join(r.name for r in presets)
        return f"저장된 프리셋: {names}"

    def get_preset_params(self, name: str) -> dict | None:
        with Session(self.engine) as session:
            preset = session.scalars(
                select(SearchPreset).where(SearchPreset.name == name)
            ).first()

        if not preset:
            return None
        params = preset.params
        return json.loads(params) if isinstance(params, str) else params

    def get_recommended_jobs(
        self,
        skills: list[str],
        rows: list[JobCandidate],
        top_k: int = 15,
    ) -> list[JobCandidate]:
        """전달된 rows에서 skill_tags 매칭 점수 기준 상위 top_k개 반환 (detail 없는 공고 제외)."""
        skills_lower = {s.lower() for s in skills}

        def score(row: JobCandidate) -> int:
            return sum(1 for tag in row.skill_tags if tag.text.lower() in skills_lower)

        with_detail = [r for r in rows if r.fetched_at is not None]
        scored = sorted(with_detail, key=score, reverse=True)
        return scored[:top_k]
