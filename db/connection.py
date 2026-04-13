import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from db.models import metadata

load_dotenv()


def get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL이 .env에 설정되지 않았습니다.")
    return create_engine(db_url)


def create_tables():
    engine = get_engine()
    metadata.create_all(engine)
