import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    expected_database = settings.test_database_url.database
    engine = create_engine(settings.test_database_url)

    with engine.connect() as connection:
        connected_database = connection.execute(text("SELECT current_database()")).scalar_one()

    if connected_database != expected_database:
        engine.dispose()
        raise RuntimeError(
            "Refusing to run database tests: connected to database "
            f"{connected_database!r}, but expected the dedicated test database "
            f"{expected_database!r}. This guard exists specifically to stop "
            "write/rollback tests from ever running against the development "
            "database due to a configuration mistake."
        )

    yield engine
    engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine)


@pytest.fixture
def db_session(test_engine):
    """A transactional ORM Session for PostgreSQL integration tests.

    One connection, one outer transaction, opened here and *always* rolled
    back in the `finally` block below -- regardless of what the test did,
    including an explicit `session.commit()`. That is only safe because the
    session is bound with `join_transaction_mode="create_savepoint"`: every
    unit of work the Session itself manages (including any `commit()` a test
    calls) is wrapped in a SAVEPOINT rather than the connection's real
    transaction, so a commit can only release that SAVEPOINT -- it can never
    reach past the outer transaction this fixture owns and rolls back.

    A separate, throwaway connection checks that the schema already exists
    (created by Alembic, never by this fixture) before the real connection
    used for the test is ever opened.
    """
    with test_engine.connect() as probe_connection:
        existing_tables = set(inspect(probe_connection).get_table_names())

    missing_tables = [
        table for table in ("securities", "daily_price_bars") if table not in existing_tables
    ]
    if missing_tables:
        raise RuntimeError(
            f"Missing table(s) {missing_tables} in {test_engine.url.database!r}. "
            "Run `alembic -x target=test upgrade head` before running these tests."
        )

    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
