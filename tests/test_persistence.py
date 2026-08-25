import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from langgraph_agent_lab.persistence import build_checkpointer


def test_build_checkpointer_memory():
    cp = build_checkpointer("memory")
    assert isinstance(cp, MemorySaver)


def test_build_checkpointer_none():
    cp = build_checkpointer("none")
    assert cp is None


def test_build_checkpointer_sqlite(tmp_path):
    db_file = tmp_path / "test_checkpoints.db"
    cp = build_checkpointer("sqlite", database_url=str(db_file))
    assert isinstance(cp, SqliteSaver)


def test_build_checkpointer_invalid():
    with pytest.raises(ValueError, match="Unknown checkpointer kind"):
        build_checkpointer("invalid_kind")


def test_build_checkpointer_postgres_not_implemented():
    with pytest.raises(NotImplementedError):
        build_checkpointer("postgres")
