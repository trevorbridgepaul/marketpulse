import pytest
from sqlalchemy import text

from app.database import session_scope


def test_rollback_discards_ddl_and_dml_on_exception(test_session_factory) -> None:
    with pytest.raises(RuntimeError), session_scope(test_session_factory) as session:
        session.execute(text("CREATE TABLE rollback_probe (id INTEGER)"))
        session.execute(text("INSERT INTO rollback_probe VALUES (1)"))
        raise RuntimeError("simulated failure mid-transaction")

    with session_scope(test_session_factory) as session:
        table_exists = session.execute(
            text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'rollback_probe'"
                ")"
            )
        ).scalar_one()

    assert table_exists is False
