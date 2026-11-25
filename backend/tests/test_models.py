from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import configure_mappers

from app.models import Base, DailyPriceBar, Security


def test_securities_table_registered() -> None:
    assert "securities" in Base.metadata.tables


def test_daily_price_bars_table_registered() -> None:
    assert "daily_price_bars" in Base.metadata.tables


def test_securities_columns() -> None:
    columns = Security.__table__.columns

    assert isinstance(columns["id"].type, BigInteger)
    assert columns["id"].primary_key is True
    assert columns["id"].nullable is False

    for name in ("symbol", "name", "exchange"):
        assert isinstance(columns[name].type, Text)
        assert columns[name].nullable is False

    assert isinstance(columns["is_active"].type, Boolean)
    assert columns["is_active"].nullable is False

    for name in ("created_at", "updated_at"):
        assert isinstance(columns[name].type, DateTime)
        assert columns[name].type.timezone is True
        assert columns[name].nullable is False
        assert columns[name].server_default is not None


def test_securities_id_is_identity_always() -> None:
    column = Security.__table__.columns["id"]

    assert column.identity is not None
    assert column.identity.always is True


def test_securities_updated_at_has_no_onupdate_hook() -> None:
    assert Security.__table__.columns["updated_at"].onupdate is None


def test_securities_symbol_unique_constraint() -> None:
    unique_constraints = {
        c.name: c for c in Security.__table__.constraints if isinstance(c, UniqueConstraint)
    }

    assert "uq_securities_symbol" in unique_constraints
    assert {col.name for col in unique_constraints["uq_securities_symbol"].columns} == {"symbol"}


def test_daily_price_bars_columns() -> None:
    columns = DailyPriceBar.__table__.columns

    assert isinstance(columns["id"].type, BigInteger)
    assert columns["id"].primary_key is True
    assert columns["id"].nullable is False

    assert isinstance(columns["security_id"].type, BigInteger)
    assert columns["security_id"].nullable is False

    assert isinstance(columns["session_date"].type, Date)
    assert columns["session_date"].nullable is False

    for name in ("open", "high", "low", "close"):
        assert isinstance(columns[name].type, Numeric)
        assert columns[name].type.precision == 12
        assert columns[name].type.scale == 4
        assert columns[name].nullable is False

    assert isinstance(columns["volume"].type, BigInteger)
    assert columns["volume"].nullable is False

    assert isinstance(columns["data_provider"].type, Text)
    assert columns["data_provider"].nullable is False

    assert isinstance(columns["feed"].type, Text)
    assert columns["feed"].nullable is False

    for name in ("created_at", "updated_at"):
        assert isinstance(columns[name].type, DateTime)
        assert columns[name].type.timezone is True
        assert columns[name].nullable is False
        assert columns[name].server_default is not None


def test_daily_price_bars_id_is_identity_always() -> None:
    column = DailyPriceBar.__table__.columns["id"]

    assert column.identity is not None
    assert column.identity.always is True


def test_daily_price_bars_updated_at_has_no_onupdate_hook() -> None:
    assert DailyPriceBar.__table__.columns["updated_at"].onupdate is None


def test_daily_price_bars_security_id_foreign_key() -> None:
    column = DailyPriceBar.__table__.columns["security_id"]
    foreign_keys = list(column.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "securities.id"


def test_daily_price_bars_unique_constraint() -> None:
    unique_constraints = {
        c.name: c for c in DailyPriceBar.__table__.constraints if isinstance(c, UniqueConstraint)
    }

    assert "uq_daily_price_bars_security_session" in unique_constraints
    assert {
        col.name for col in unique_constraints["uq_daily_price_bars_security_session"].columns
    } == {"security_id", "session_date"}


def test_daily_price_bars_ohlcv_check_constraints() -> None:
    check_constraints = {
        c.name: str(c.sqltext)
        for c in DailyPriceBar.__table__.constraints
        if isinstance(c, CheckConstraint)
    }

    assert check_constraints["ck_daily_price_bars_open_positive"] == "open > 0"
    assert check_constraints["ck_daily_price_bars_high_positive"] == "high > 0"
    assert check_constraints["ck_daily_price_bars_low_positive"] == "low > 0"
    assert check_constraints["ck_daily_price_bars_close_positive"] == "close > 0"
    assert check_constraints["ck_daily_price_bars_volume_nonnegative"] == "volume >= 0"
    assert (
        check_constraints["ck_daily_price_bars_high_is_max"]
        == "high >= open AND high >= low AND high >= close"
    )
    assert (
        check_constraints["ck_daily_price_bars_low_is_min"]
        == "low <= open AND low <= high AND low <= close"
    )


def test_daily_price_bars_provider_and_feed_check_constraints() -> None:
    check_constraints = {
        c.name: str(c.sqltext)
        for c in DailyPriceBar.__table__.constraints
        if isinstance(c, CheckConstraint)
    }

    assert (
        check_constraints["ck_daily_price_bars_data_provider_alpaca"] == "data_provider = 'alpaca'"
    )
    assert check_constraints["ck_daily_price_bars_feed_iex"] == "feed = 'iex'"


def test_security_daily_price_bars_relationship_is_bidirectional() -> None:
    configure_mappers()

    security_rel = Security.__mapper__.relationships["daily_price_bars"]
    assert security_rel.mapper.class_ is DailyPriceBar
    assert security_rel.back_populates == "security"

    bar_rel = DailyPriceBar.__mapper__.relationships["security"]
    assert bar_rel.mapper.class_ is Security
    assert bar_rel.back_populates == "daily_price_bars"


def test_no_unapproved_indexes() -> None:
    assert Security.__table__.indexes == set()
    assert DailyPriceBar.__table__.indexes == set()
