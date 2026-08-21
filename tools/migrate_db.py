from db.connection import get_engine, migrate, migrate_bigint, migrate_location_length


def migrate_db() -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션한다. 이미 완료된 경우 skip.

    주의: 실서비스 DB에서 실행 전 반드시 백업할 것.
    """
    try:
        engine = get_engine()
        result1 = migrate(engine)
        result2 = migrate_bigint(engine)
        result3 = migrate_location_length(engine)
        return f"{result1} / {result2} / {result3}"
    except Exception as e:
        return f"마이그레이션 오류: {e}"



if __name__ == "__main__":
    migrate_db()