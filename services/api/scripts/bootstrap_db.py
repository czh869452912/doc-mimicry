from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from docagent_api.db import get_database_url


def main() -> int:
    engine = create_engine(get_database_url())
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(44500613)"))
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        if "alembic_version" in tables:
            return 0
        if {"tasks", "sessions", "timeline_events", "raw_runtime_events"}.issubset(tables):
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0001')"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
