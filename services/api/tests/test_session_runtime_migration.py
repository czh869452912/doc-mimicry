from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0002_session_runtime_binding.py"
)
SPEC = spec_from_file_location("session_runtime_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
session_runtime_migration = module_from_spec(SPEC)
SPEC.loader.exec_module(session_runtime_migration)


class _FakeInspector:
    def __init__(self, existing_columns: set[str]) -> None:
        self.existing_columns = existing_columns

    def get_columns(self, table_name: str) -> list[dict[str, str]]:
        assert table_name == "sessions"
        return [{"name": column_name} for column_name in self.existing_columns]


class _FakeOp:
    def __init__(self) -> None:
        self.added_columns: list[str] = []

    def get_bind(self) -> object:
        return object()

    def add_column(self, table_name: str, column) -> None:
        assert table_name == "sessions"
        self.added_columns.append(column.name)


def test_session_runtime_migration_skips_columns_that_already_exist(monkeypatch) -> None:
    fake_op = _FakeOp()

    monkeypatch.setattr(session_runtime_migration, "op", fake_op)
    monkeypatch.setattr(
        session_runtime_migration.sa,
        "inspect",
        lambda _bind: _FakeInspector({"runtime"}),
    )

    session_runtime_migration.upgrade()

    assert fake_op.added_columns == ["runtime_session_id", "celery_task_id"]
