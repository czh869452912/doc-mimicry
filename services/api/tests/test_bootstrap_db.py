from sqlalchemy import create_engine, inspect, text
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_db.py"
SPEC = spec_from_file_location("bootstrap_db", BOOTSTRAP_PATH)
assert SPEC and SPEC.loader
bootstrap_db = module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap_db)


def test_bootstrap_stamps_legacy_create_tables_database(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        for table in ["tasks", "sessions", "timeline_events", "raw_runtime_events"]:
            connection.execute(text(f"CREATE TABLE {table} (id TEXT PRIMARY KEY)"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    assert bootstrap_db.main() == 0

    with engine.connect() as connection:
        assert "alembic_version" in inspect(connection).get_table_names()
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0001"
