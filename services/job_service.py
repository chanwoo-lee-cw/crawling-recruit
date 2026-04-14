import json
from datetime import datetime, timezone
from sqlalchemy import text, select
from sqlalchemy.dialects.mysql import insert

from db.models import jobs_table, applications_table, search_presets_table, job_details_table

ALLOWED_PRESET_KEYS = {"job_group_id", "job_ids", "years", "locations", "limit_pages"}


class JobService:
    EMPLOYMENT_TYPE_MAP = {
        "정규직": "regular",
        "인턴": "intern",
        "계약직": "contract",
    }

    def __init__(self, engine):
        self.engine = engine

    def _parse_job(self, raw: dict) -> dict:
        address = raw.get("address") or {}
        location_str = address.get("location", "")
        district = address.get("district", "")
        location = f"{location_str} {district}".strip() if district else location_str

        category_tag = raw.get("category_tag") or {}
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        create_time = raw.get("create_time")
        created_at = datetime.fromisoformat(create_time) if create_time else None

        return {
            "id": raw["id"],
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

    def _parse_application(self, raw: dict) -> dict:
        apply_time = raw.get("apply_time")
        return {
            "id": raw["id"],
            "job_id": raw["job_id"],
            "status": raw["status"],
            "apply_time": datetime.fromisoformat(apply_time) if apply_time else None,
            "synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    def upsert_jobs(self, raw_jobs: list[dict], full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

        rows = [self._parse_job(j) for j in raw_jobs]
        synced_ids = {r["id"] for r in rows}

        with self.engine.connect() as conn:
            # Count pre-existing rows to distinguish inserts from updates
            existing_ids = set(conn.execute(
                select(jobs_table.c.id).where(jobs_table.c.id.in_(synced_ids))
            ).scalars().all())
            new_count = len(synced_ids - existing_ids)

            stmt = insert(jobs_table).values(rows)
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
                    "IF(new.company_name <> company_name OR new.title <> title "
                    "OR new.location <> location OR new.employment_type <> employment_type "
                    "OR new.annual_from <> annual_from OR new.annual_to <> annual_to, "
                    "NOW(), updated_at)"
                ),
            }
            upsert_stmt = stmt.on_duplicate_key_update(**update_dict)
            result = conn.execute(upsert_stmt)
            conn.commit()

            # full_sync일 때 비활성화 처리
            if full_sync and synced_ids:
                conn.execute(
                    jobs_table.update()
                    .where(jobs_table.c.id.not_in(synced_ids))
                    .where(jobs_table.c.is_active == True)
                    .values(is_active=False)
                )
                conn.commit()

            # rowcount = new_count*1 + updated*2 + unchanged*0
            updated_count = (result.rowcount - new_count) // 2
            unchanged_count = len(rows) - new_count - updated_count
            return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"

    def upsert_applications(self, raw_apps: list[dict]) -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"

        rows = [self._parse_application(a) for a in raw_apps]

        with self.engine.connect() as conn:
            stmt = insert(applications_table).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                status=stmt.inserted.status,
                synced_at=stmt.inserted.synced_at,
            )
            conn.execute(upsert_stmt)
            conn.commit()

        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    def upsert_job_details(self, details: list[dict]) -> str:
        if not details:
            return "완료: 0개 처리"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {
                "job_id": d["job_id"],
                "requirements": d.get("requirements"),
                "preferred_points": d.get("preferred_points"),
                "skill_tags": d.get("skill_tags", []),
                "fetched_at": now,
            }
            for d in details
        ]
        with self.engine.connect() as conn:
            stmt = insert(job_details_table).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                requirements=stmt.inserted.requirements,
                preferred_points=stmt.inserted.preferred_points,
                skill_tags=stmt.inserted.skill_tags,
                fetched_at=stmt.inserted.fetched_at,
            )
            conn.execute(upsert_stmt)
            conn.commit()
        return f"완료: {len(rows)}개 처리"

    def get_jobs_without_details(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[int]:
        """job_details가 없는 공고의 job_id 목록 반환."""
        if job_ids is not None:
            candidates = job_ids[:limit] if limit is not None else job_ids
            with self.engine.connect() as conn:
                existing = set(conn.execute(
                    select(job_details_table.c.job_id).where(
                        job_details_table.c.job_id.in_(candidates)
                    )
                ).scalars().all())
            return [jid for jid in candidates if jid not in existing]
        # Use bound parameters for LIMIT (SQL injection prevention)
        if limit is not None:
            query = text("""
                SELECT j.id FROM jobs j
                LEFT JOIN job_details jd ON j.id = jd.job_id
                WHERE jd.job_id IS NULL AND j.is_active = TRUE
                ORDER BY j.id
                LIMIT :limit
            """)
            params = {"limit": limit}
        else:
            query = text("""
                SELECT j.id FROM jobs j
                LEFT JOIN job_details jd ON j.id = jd.job_id
                WHERE jd.job_id IS NULL AND j.is_active = TRUE
                ORDER BY j.id
            """)
            params = {}
        with self.engine.connect() as conn:
            return list(conn.execute(query, params).scalars().all())

    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        query = text("""
            SELECT j.id, j.company_name, j.title, j.location, j.employment_type
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            WHERE a.job_id IS NULL
              AND j.is_active = TRUE
              AND (:job_group_id IS NULL OR j.job_group_id = :job_group_id)
              AND (:location IS NULL OR j.location LIKE CONCAT('%', :location, '%'))
              AND (:employment_type IS NULL OR j.employment_type = :employment_type)
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(query, {
                "job_group_id": job_group_id,
                "location": location,
                "employment_type": employment_type,
                "limit": limit,
            }).mappings().all()

        if not rows:
            return "미지원 공고가 없습니다."

        lines = ["| 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|"]
        for row in rows:
            link = f"https://www.wanted.co.kr/wd/{row['id']}"
            lines.append(
                f"| {row['company_name']} | {row['title']} | {row['location']} | {link} |"
            )
        lines.append(f"총 {len(rows)}개의 미지원 공고")
        return "\n".join(lines)

    def get_unapplied_job_rows(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
    ) -> list[dict]:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        query = text("""
            SELECT j.id, j.company_name, j.title, j.location, j.employment_type,
                   jd.requirements, jd.preferred_points, jd.skill_tags, jd.fetched_at
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            LEFT JOIN job_details jd ON j.id = jd.job_id
            WHERE a.job_id IS NULL
              AND j.is_active = TRUE
              AND (:job_group_id IS NULL OR j.job_group_id = :job_group_id)
              AND (:location IS NULL OR j.location LIKE CONCAT('%', :location, '%'))
              AND (:employment_type IS NULL OR j.employment_type = :employment_type)
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, {
                "job_group_id": job_group_id,
                "location": location,
                "employment_type": employment_type,
            }).mappings().all()
        return [dict(r) for r in rows]

    def save_preset(self, name: str, params: dict) -> str:
        invalid_keys = set(params.keys()) - ALLOWED_PRESET_KEYS
        if invalid_keys:
            raise ValueError(
                f"유효하지 않은 파라미터 키: {sorted(invalid_keys)}. "
                f"허용 키: {', '.join(sorted(ALLOWED_PRESET_KEYS))}"
            )

        row = {
            "name": name,
            "params": json.dumps(params, ensure_ascii=False),
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        with self.engine.connect() as conn:
            stmt = insert(search_presets_table).values([row])
            upsert_stmt = stmt.on_duplicate_key_update(
                params=stmt.inserted.params,
                created_at=stmt.inserted.created_at,
            )
            conn.execute(upsert_stmt)
            conn.commit()

        return f"프리셋 '{name}' 저장 완료"

    def list_presets(self) -> str:
        with self.engine.connect() as conn:
            rows = conn.execute(
                search_presets_table.select().order_by(search_presets_table.c.created_at)
            ).mappings().all()

        if not rows:
            return "저장된 프리셋이 없습니다."
        names = ", ".join(r["name"] for r in rows)
        return f"저장된 프리셋: {names}"

    def get_recommended_jobs(
        self,
        skills: list[str],
        rows: list[dict],
        top_k: int = 15,
    ) -> list[dict]:
        """전달된 rows에서 skill_tags 매칭 점수 기준 상위 top_k개 반환 (detail 없는 공고 제외)."""
        skills_lower = {s.lower() for s in skills}

        def score(row: dict) -> int:
            tags = row.get("skill_tags") or []
            return sum(1 for t in tags if t.get("text", "").lower() in skills_lower)

        with_detail = [r for r in rows if r.get("fetched_at") is not None]
        scored = sorted(with_detail, key=score, reverse=True)
        return scored[:top_k]

    def get_preset_params(self, name: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                search_presets_table.select().where(search_presets_table.c.name == name)
            ).mappings().first()

        if not row:
            return None
        params = row["params"]
        return json.loads(params) if isinstance(params, str) else params
