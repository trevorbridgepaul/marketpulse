import pytest
from sqlalchemy import create_engine, text
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
