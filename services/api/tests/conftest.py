import os

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from docagent_api.db import Base, create_session_factory
from docagent_api.state import DocAgentState


@pytest.fixture(scope="session")
def postgres_container():
    """Start a Postgres container once per test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_engine(postgres_container):
    """Create SQLAlchemy engine pointing at the test container."""
    url = postgres_container.get_connection_url()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _db_isolation(pg_engine):
    """Set DATABASE_URL for all tests; truncate all tables after each test."""
    os.environ["DATABASE_URL"] = pg_engine.url.render_as_string(hide_password=False)
    yield
    os.environ.pop("DATABASE_URL", None)
    with pg_engine.connect() as conn:
        conn.execute(text(
            "TRUNCATE raw_runtime_events, timeline_events, sessions, tasks "
            "RESTART IDENTITY CASCADE"
        ))
        conn.commit()


@pytest.fixture
def pg_state(pg_engine, tmp_path):
    """DocAgentState backed by the test Postgres container."""
    state = DocAgentState.__new__(DocAgentState)
    state.root = tmp_path
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    state._engine = pg_engine
    state._Session = create_session_factory(pg_engine)
    yield state
