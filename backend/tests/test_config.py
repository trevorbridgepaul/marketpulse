from app.config import get_settings


def test_settings_load_required_values_from_environment() -> None:
    settings = get_settings()

    assert settings.postgres_user
    assert settings.postgres_db
    assert settings.postgres_port > 0


def test_database_url_uses_psycopg_driver() -> None:
    settings = get_settings()

    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.database_url.database == settings.postgres_db


def test_test_database_url_is_isolated_from_dev_database() -> None:
    settings = get_settings()

    assert settings.test_database_url.database == f"{settings.postgres_db}_test"
    assert settings.test_database_url.database != settings.database_url.database


def test_settings_do_not_expose_password_in_repr_or_str() -> None:
    settings = get_settings()
    secret = settings.postgres_password.get_secret_value()

    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert secret not in repr(settings.database_url)
