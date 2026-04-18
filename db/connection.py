import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from db.models import Base


def get_engine():
    load_dotenv()
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL이 .env에 설정되지 않았습니다.")
    return create_engine(db_url)


def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)


from sqlalchemy import text


def migrate(engine) -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션. 멱등: 이미 완료된 경우 skip."""
    with engine.connect() as conn:
        result = conn.execute(text("SHOW COLUMNS FROM jobs LIKE 'platform_id'"))
        if result.fetchone():
            return "마이그레이션 이미 완료됨"

        # 1. FK 제약 제거
        conn.execute(text("ALTER TABLE applications DROP FOREIGN KEY applications_ibfk_1"))
        conn.execute(text("ALTER TABLE job_details DROP FOREIGN KEY job_details_ibfk_1"))
        conn.execute(text("ALTER TABLE job_skips DROP FOREIGN KEY job_skips_ibfk_1"))

        # 2. jobs: PK DROP + id를 platform_id로 rename (AUTO_INCREMENT 제거 포함)
        conn.execute(text(
            "ALTER TABLE jobs DROP PRIMARY KEY, CHANGE COLUMN id platform_id INT NOT NULL"
        ))

        # 3. internal_id AUTO_INCREMENT PK 추가
        conn.execute(text(
            "ALTER TABLE jobs ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST"
        ))

        # 4. source 컬럼 + UNIQUE KEY
        conn.execute(text(
            "ALTER TABLE jobs ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted'"
        ))
        conn.execute(text(
            "ALTER TABLE jobs ADD UNIQUE KEY uq_source_platform (source, platform_id)"
        ))

        # 5. applications: FK 업데이트 전 job_id 값 재매핑
        conn.execute(text(
            "UPDATE applications a JOIN jobs j ON a.job_id = j.platform_id AND j.source = 'wanted' "
            "SET a.job_id = j.internal_id"
        ))
        conn.execute(text(
            "UPDATE job_details jd JOIN jobs j ON jd.job_id = j.platform_id AND j.source = 'wanted' "
            "SET jd.job_id = j.internal_id"
        ))
        conn.execute(text(
            "UPDATE job_skips js JOIN jobs j ON js.job_id = j.platform_id AND j.source = 'wanted' "
            "SET js.job_id = j.internal_id"
        ))

        # 6. applications 테이블 PK 교체
        conn.execute(text("ALTER TABLE applications DROP PRIMARY KEY, CHANGE COLUMN id platform_id INT NOT NULL"))
        conn.execute(text("ALTER TABLE applications ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST"))
        conn.execute(text("ALTER TABLE applications ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted'"))
        conn.execute(text("ALTER TABLE applications ADD UNIQUE KEY uq_app_source_platform (source, platform_id)"))

        # 7. FK 재추가
        conn.execute(text(
            "ALTER TABLE applications ADD CONSTRAINT applications_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))
        conn.execute(text(
            "ALTER TABLE job_details ADD CONSTRAINT job_details_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))
        conn.execute(text(
            "ALTER TABLE job_skips ADD CONSTRAINT job_skips_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))

        conn.commit()

    return "마이그레이션 완료"
