from sqlalchemy import text

from app.database import session_scope


def test_uncommitted_write_does_not_persist(test_session_factory) -> None:
    """A write with no exception and no explicit commit() is discarded."""
    with session_scope(test_session_factory) as session:
        session.execute(text("CREATE TABLE commit_ownership_probe (id INTEGER)"))
        session.execute(text("INSERT INTO commit_ownership_probe VALUES (1)"))
        # Deliberately: no exception, no session.commit().

    with session_scope(test_session_factory) as session:
        table_exists = session.execute(
            text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'commit_ownership_probe'"
                ")"
            )
        ).scalar_one()

    assert table_exists is False


def test_explicitly_committed_write_persists(test_session_factory) -> None:
    """A write followed by an explicit commit() is visible afterward."""
    try:
        with session_scope(test_session_factory) as session:
            session.execute(text("CREATE TABLE commit_persistence_probe (id INTEGER)"))
            session.execute(text("INSERT INTO commit_persistence_probe VALUES (1)"))
            session.commit()

        with session_scope(test_session_factory) as session:
            row_count = session.execute(
                text("SELECT COUNT(*) FROM commit_persistence_probe")
            ).scalar_one()

        assert row_count == 1
    finally:
        with session_scope(test_session_factory) as session:
            session.execute(text("DROP TABLE IF EXISTS commit_persistence_probe"))
            session.commit()
