import json
import re
from datetime import datetime, timezone

from db.models import SearchPreset
from services.wanted.wanted_constants import WANTED
from services.remember.remember_constants import REMEMBER
from services.nhn.nhn_constants import NHN, NHN_JOB_BASE_URL
from services.naver.naver_constants import NAVER, NAVER_JOB_BASE_URL
from db.repositories.search_preset_repository import SearchPresetRepository
from db.repositories.job_detail_repository import JobDetailRepository
from db.repositories.application_repository import ApplicationRepository
from db.repositories.job_skip_repository import JobSkipRepository
from db.repositories.job_evaluation_repository import JobEvaluationRepository
from db.repositories.job_repository import JobRepository
from db.transaction import transactional, get_current_session
from domain import JobCandidate, JobDetail

ALLOWED_PRESET_KEYS = {
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    "job_category_names", "min_experience", "max_experience", "source",
    "job_series_ids",
}
WANTED_JOB_BASE_URL = "https://www.wanted.co.kr/wd"
REMEMBER_JOB_BASE_URL = "https://career.rememberapp.co.kr/job/posting"

JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
    NHN: NHN_JOB_BASE_URL,
    NAVER: NAVER_JOB_BASE_URL,
}


def build_job_url(source: str, platform_id: int) -> str:
    base_url = JOB_BASE_URLS.get(source, WANTED_JOB_BASE_URL)
    if base_url.endswith("="):
        return f"{base_url}{platform_id}"
    return f"{base_url}/{platform_id}"


class JobService:
    EMPLOYMENT_TYPE_MAP = {
        "정규직": "regular",
        "정규": "regular",
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
            "source": WANTED,
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
            "source": REMEMBER,
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

    def _parse_nhn_job(self, raw: dict) -> dict:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        emp_type_raw = (raw.get("employeeType") or {}).get("name")
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_type_raw) if emp_type_raw else None
        return {
            "source": NHN,
            "platform_id": int(raw["id"]),
            "company_id": None,
            "company_name": raw["corporation"]["name"],
            "title": raw["name"],
            "location": None,
            "employment_type": employment_type,
            "annual_from": None,
            "annual_to": None,
            "job_group_id": None,
            "category_tag_id": None,
            "is_active": True,
            "created_at": None,
            "synced_at": now,
            "updated_at": None,
        }

    def _parse_nhn_applications(self, raw_apps: list[dict]) -> list[dict]:
        result = []
        for raw in raw_apps:
            if raw.get("finalSubmitYn") != "Y":
                continue
            apply_time_str = raw.get("finalSubmitDatetime")
            if apply_time_str and len(apply_time_str) == 16:
                apply_time_str = apply_time_str + ":00"
            result.append({
                "job_platform_id": int(raw["jobPostingId"]),
                "platform_id": int(raw["applicationId"]),
                "status": raw.get("displayStepButtonCd", ""),
                "apply_time_str": apply_time_str,
            })
        return result

    def _parse_job(self, raw: dict, source: str = WANTED) -> dict:
        if source == REMEMBER:
            return self._parse_remember_job(raw)
        if source == NHN:
            return self._parse_nhn_job(raw)
        return self._parse_wanted_job(raw)

    def _parse_wanted_applications(self, raw_apps: list[dict]) -> list[dict]:
        return [
            {
                "job_platform_id": app["job_id"],
                "platform_id": app["id"],
                "status": app["status"],
                "apply_time_str": app.get("apply_time"),
            }
            for app in raw_apps
        ]

    def _parse_remember_applications(self, raw_apps: list[dict]) -> list[dict]:
        result = []
        for app in raw_apps:
            application = app.get("application")
            if not application:
                continue
            result.append({
                "job_platform_id": app["id"],
                "platform_id": application["id"],
                "status": application["status"],
                "apply_time_str": application.get("applied_at"),
            })
        return result

    def _parse_applications(self, raw_apps: list[dict], source: str) -> list[dict]:
        if source == REMEMBER:
            return self._parse_remember_applications(raw_apps)
        if source == NHN:
            return self._parse_nhn_applications(raw_apps)
        return self._parse_wanted_applications(raw_apps)

    @transactional()
    def upsert_jobs(self, raw_jobs: list[dict], source: str = WANTED, full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"
        rows = [self._parse_job(j, source=source) for j in raw_jobs]
        synced_pairs = [(source, r["platform_id"]) for r in rows]
        session = get_current_session()
        repo = JobRepository(session)
        existing_pairs = repo.find_existing_pairs(source, [r["platform_id"] for r in rows])
        new_count = len(rows) - len(existing_pairs)
        result = repo.upsert(rows)
        if full_sync and synced_pairs:
            repo.deactivate_removed(source, synced_pairs)
        updated_count = (result.rowcount - new_count) // 2
        unchanged_count = len(rows) - new_count - updated_count
        return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"

    @transactional()
    def upsert_applications(self, raw_apps: list[dict], source: str = WANTED) -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        parsed = self._parse_applications(raw_apps, source)
        if not parsed:
            return "지원현황 동기화 완료: 총 0건"
        job_platform_ids = [p["job_platform_id"] for p in parsed]
        session = get_current_session()
        job_id_map = JobRepository(session).find_platform_id_map(source, job_platform_ids)
        rows = []
        for p in parsed:
            job_internal_id = job_id_map.get(p["job_platform_id"])
            if job_internal_id is None:
                continue
            apply_time = (
                datetime.fromisoformat(p["apply_time_str"]).replace(tzinfo=None)
                if p["apply_time_str"] else None
            )
            rows.append({
                "source": source,
                "platform_id": p["platform_id"],
                "job_id": job_internal_id,
                "status": p["status"],
                "apply_time": apply_time,
                "synced_at": now,
            })
        if not rows:
            return "지원현황 동기화 완료: 총 0건"
        ApplicationRepository(session).upsert(rows)
        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    @transactional()
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
        JobDetailRepository(get_current_session()).upsert(rows)
        return f"완료: {len(rows)}개 처리"

    @transactional()
    def upsert_remember_details(self, raw_jobs: list[dict]) -> None:
        if not raw_jobs:
            return
        platform_ids = [r["id"] for r in raw_jobs]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session = get_current_session()
        internal_id_map = JobRepository(session).find_platform_id_map(REMEMBER, platform_ids)
        detail_rows = []
        for raw in raw_jobs:
            internal_id = internal_id_map.get(raw["id"])
            if not internal_id:
                continue
            categories = raw.get("job_categories") or []
            skill_tags = [{"text": c["level2"]} for c in categories if c.get("level2")]
            detail_rows.append({
                "job_id": internal_id,
                "requirements": raw.get("qualifications"),
                "preferred_points": raw.get("preferred_qualifications"),
                "skill_tags": skill_tags,
                "fetched_at": now,
            })
        if not detail_rows:
            return
        JobDetailRepository(session).upsert(detail_rows)

    @transactional()
    def get_jobs_without_details(
        self,
        source: str = WANTED,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[tuple[int, int]]:
        session = get_current_session()
        repo = JobRepository(session)
        if job_ids is not None:
            existing = JobDetailRepository(session).find_existing_job_ids(job_ids)
            missing = [jid for jid in job_ids if jid not in existing]
            if limit is not None:
                missing = missing[:limit]
            return repo.find_internal_platform_pairs(missing)
        return repo.find_without_details(source=source, limit=limit)

    @transactional()
    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        rows = JobRepository(get_current_session()).find_unapplied(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            limit=limit,
        )
        if not rows:
            return "미지원 공고가 없습니다."
        lines = ["| internal_id | 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|---|"]
        for row in rows:
            link = build_job_url(row["source"], row["platform_id"])
            lines.append(
                f"| {row['internal_id']} | {row['company_name']} | {row['title']} | {row['location']} | {link} |"
            )
        lines.append(f"총 {len(rows)}개의 미지원 공고")
        return "\n".join(lines)

    @transactional()
    def get_unapplied_job_rows(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        include_evaluated: bool = False,
        source: str | None = None,
    ) -> list[JobCandidate]:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        rows = JobRepository(get_current_session()).find_unapplied_with_details(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            include_evaluated=include_evaluated,
            source=source,
        )
        return [JobCandidate.from_row(r) for r in rows]

    @staticmethod
    def _extract_years_range(text: str | None) -> tuple[int | None, int | None]:
        """requirements 텍스트에서 경력 범위 추출. (min, max) 반환, None은 제한 없음."""
        if not text:
            return None, None
        if re.search(r'경력\s*무관|신입.*경력|경력.*신입|무관', text):
            return None, None
        m = re.search(r'(\d+)\s*년\s*[~～]\s*(\d+)\s*년', text)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.search(r'(\d+)\s*[~～]\s*(\d+)\s*년', text)
        if m:
            return int(m.group(1)), int(m.group(2))
        m = re.search(r'(\d+)\s*년\s*이상', text)
        if m:
            return int(m.group(1)), None
        m = re.search(r'(\d+)\s*년\s*이하', text)
        if m:
            return None, int(m.group(1))
        return None, None

    @staticmethod
    def filter_by_years(candidates: list[JobCandidate], years: int) -> list[JobCandidate]:
        """주어진 경력(년수)으로 지원 가능한 공고만 반환. 경력 정보 없으면 포함."""
        result = []
        for c in candidates:
            req_min, req_max = JobService._extract_years_range(c.requirements)
            if req_min is None and req_max is None:
                result.append(c)
            elif req_min is not None and years < req_min:
                continue
            elif req_max is not None and years > req_max:
                continue
            else:
                result.append(c)
        return result

    @transactional()
    def skip_jobs(self, job_ids: list[int], reason: str | None = None) -> str:
        if not job_ids:
            return "제외할 공고 ID를 입력해주세요."
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [{"job_id": jid, "reason": reason, "skipped_at": now} for jid in job_ids]
        JobSkipRepository(get_current_session()).upsert(rows)
        suffix = f" (사유: {reason})" if reason else ""
        return f"{len(job_ids)}개 공고 제외 완료{suffix}"

    @transactional()
    def save_job_evaluations(self, evaluations: list[dict]) -> str:
        if not evaluations:
            return "0개 처리"
        invalid = [e.get("verdict") for e in evaluations if e.get("verdict") not in self.VALID_VERDICTS]
        if invalid:
            raise ValueError(f"유효하지 않은 verdict: {invalid}. 허용 값: good, pass, skip")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {"job_id": e["job_id"], "verdict": e["verdict"], "evaluated_at": now}
            for e in evaluations
        ]
        JobEvaluationRepository(get_current_session()).upsert(rows)
        return f"{len(rows)}개 평가 저장 완료"

    @transactional()
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
        SearchPresetRepository(get_current_session()).upsert(row)
        return f"프리셋 '{name}' 저장 완료"

    @transactional()
    def list_presets(self) -> str:
        presets = SearchPresetRepository(get_current_session()).find_all()
        if not presets:
            return "저장된 프리셋이 없습니다."
        return f"저장된 프리셋: {', '.join(r.name for r in presets)}"

    @transactional()
    def get_preset_params(self, name: str) -> SearchPreset | None:
        preset: SearchPreset = SearchPresetRepository(get_current_session()).find_by_name(name.upper())
        if not preset:
            return None
        return preset

    def get_recommended_jobs(
        self,
        skills: list[str],
        rows: list[JobCandidate],
        top_k: int = 15,
    ) -> list[JobCandidate]:
        skills_lower = {s.lower() for s in skills}

        def score(row: JobCandidate) -> int:
            return sum(1 for tag in row.skill_tags if tag.text.lower() in skills_lower)

        with_detail = [r for r in rows if r.fetched_at is not None]
        scored = sorted(with_detail, key=score, reverse=True)
        return scored[:top_k]
