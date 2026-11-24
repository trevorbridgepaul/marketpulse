from sqlalchemy import text

from app.database import engine, get_session


def test_select_1_against_dev_database() -> None:
    with get_session() as session:
        result = session.execute(text("SELECT 1")).scalar_one()

    assert result == 1


def test_session_releases_connection_back_to_pool_on_success() -> None:
    assert engine.pool.checkedout() == 0

    with get_session() as session:
        session.execute(text("SELECT 1"))
        assert engine.pool.checkedout() == 1

    assert engine.pool.checkedout() == 0


def test_session_releases_connection_back_to_pool_on_exception() -> None:
    assert engine.pool.checkedout() == 0

    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    assert engine.pool.checkedout() == 0
