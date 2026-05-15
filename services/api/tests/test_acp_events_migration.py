from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "0003_acp_events.py"
)
SPEC = spec_from_file_location("acp_events_migration", MIGRATION_PATH)
assert SPEC and SPEC.loader
acp_events_migration = module_from_spec(SPEC)
SPEC.loader.exec_module(acp_events_migration)


class _FakeInspector:
    def __init__(self, tables: set[str], indexes: set[str]) -> None:
        self.tables = tables
        self.indexes = indexes

    def get_table_names(self) -> list[str]:
        return sorted(self.tables)

    def get_indexes(self, table_name: str) -> list[dict[str, str]]:
        assert table_name == "acp_events"
        return [{"name": index_name} for index_name in sorted(self.indexes)]


class _FakeOp:
    def __init__(self) -> None:
        self.created_tables: list[str] = []
        self.created_indexes: list[tuple[str, str, list[str]]] = []

    def get_bind(self) -> object:
        return object()

    def create_table(self, table_name: str, *args, **kwargs) -> None:
        self.created_tables.append(table_name)

    def create_index(self, index_name: str, table_name: str, columns: list[str]) -> None:
        self.created_indexes.append((index_name, table_name, columns))


def test_acp_events_migration_creates_table_and_index_when_missing(monkeypatch) -> None:
    fake_op = _FakeOp()

    monkeypatch.setattr(acp_events_migration, "op", fake_op)
    monkeypatch.setattr(
        acp_events_migration.sa,
        "inspect",
        lambda _bind: _FakeInspector(set(), set()),
    )

    acp_events_migration.upgrade()

    assert fake_op.created_tables == ["acp_events"]
    assert fake_op.created_indexes == [
        ("idx_acp_events_session_id", "acp_events", ["session_id", "id"])
    ]


def test_acp_events_migration_skips_existing_table_and_index(monkeypatch) -> None:
    fake_op = _FakeOp()

    monkeypatch.setattr(acp_events_migration, "op", fake_op)
    monkeypatch.setattr(
        acp_events_migration.sa,
        "inspect",
        lambda _bind: _FakeInspector({"acp_events"}, {"idx_acp_events_session_id"}),
    )

    acp_events_migration.upgrade()

    assert fake_op.created_tables == []
    assert fake_op.created_indexes == []


def test_acp_events_migration_adds_missing_index_to_existing_table(monkeypatch) -> None:
    fake_op = _FakeOp()

    monkeypatch.setattr(acp_events_migration, "op", fake_op)
    monkeypatch.setattr(
        acp_events_migration.sa,
        "inspect",
        lambda _bind: _FakeInspector({"acp_events"}, set()),
    )

    acp_events_migration.upgrade()

    assert fake_op.created_tables == []
    assert fake_op.created_indexes == [
        ("idx_acp_events_session_id", "acp_events", ["session_id", "id"])
    ]
