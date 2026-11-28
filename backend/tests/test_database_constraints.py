"""PostgreSQL integration tests proving ADR 002's constraints are actually
enforced by the database, not merely declared in `Security`/`DailyPriceBar`.

Every "expected to fail" case asserts the *exact* named constraint from the
real PostgreSQL diagnostics (`error.orig.diag.constraint_name`), not just
"some IntegrityError happened" -- a wrong column, a typo'd check, or a
constraint that silently failed to get created by the migration would all
still raise *an* IntegrityError, but not the one we actually mean to prove.

Each valid seed row is explicitly flushed before any SAVEPOINT is opened for
a deliberately-invalid insert (`session.begin_nested()` already flushes
pending changes itself before issuing the SAVEPOINT, but doing it explicitly
here keeps the seed's own success a distinct, separately-visible step from
the failure under test).

Uses only Alembic-created schema (via the `db_session` fixture in
conftest.py) -- never `Base.metadata.create_all()`/`drop_all()`.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import DailyPriceBar, Security

_VALID_SYMBOL = "TESTSEC"


def _make_security(**overrides) -> Security:
    defaults = {"symbol": _VALID_SYMBOL, "name": "Test Security", "exchange": "TEST"}
    defaults.update(overrides)
    return Security(**defaults)


def _make_daily_price_bar(security_id, **overrides) -> DailyPriceBar:
    defaults = {
        "security_id": security_id,
        "session_date": date(2026, 1, 2),
        "open": Decimal(100),
        "high": Decimal(105),
        "low": Decimal(99),
        "close": Decimal(102),
        "volume": 1_000_000,
        "data_provider": "alpaca",
        "feed": "iex",
    }
    defaults.update(overrides)
    return DailyPriceBar(**defaults)


def _constraint_name(error: IntegrityError) -> str | None:
    """The actual PostgreSQL constraint name that caused this IntegrityError,
    read from psycopg's diagnostics -- not inferred from the row we sent."""
    return getattr(getattr(error.orig, "diag", None), "constraint_name", None)


# --- transaction pattern self-test ---


def test_savepoint_session_commit_does_not_escape_outer_transaction(test_engine) -> None:
    """Verify the underlying SQLAlchemy transaction pattern `db_session` is
    built on: a Session bound with join_transaction_mode="create_savepoint"
    treats its own `commit()` as releasing a SAVEPOINT only, never the
    connection's real outer transaction.

    This test does not exercise pytest's fixture teardown machinery itself
    -- it drives the same connect/begin/sessionmaker/commit/rollback/close
    sequence directly, inline, so we can assert against a brand-new
    connection afterward. The suite's broader confidence that `db_session`
    itself behaves this way on every test comes from repeated runs,
    execution in reversed order, and zero persisted rows across the whole
    file -- not from this test re-entering the fixture.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    session.add(_make_security(symbol="LEAK_PROBE_SHOULD_NOT_PERSIST"))
    session.commit()  # join_transaction_mode="create_savepoint": releases a SAVEPOINT only

    # Same cleanup shape db_session's own finally block uses.
    session.close()
    transaction.rollback()
    connection.close()

    with test_engine.connect() as fresh_connection:
        count = fresh_connection.execute(
            text("SELECT COUNT(*) FROM securities WHERE symbol = :symbol"),
            {"symbol": "LEAK_PROBE_SHOULD_NOT_PERSIST"},
        ).scalar_one()

    assert count == 0


# --- valid inserts ---


def test_valid_security_insert_is_accepted(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    assert security.id is not None
    db_session.refresh(security)
    assert security.is_active is True
    assert security.created_at is not None
    assert security.updated_at is not None


def test_valid_daily_price_bar_insert_is_accepted(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    bar = _make_daily_price_bar(security.id)
    db_session.add(bar)
    db_session.flush()

    assert bar.id is not None
    assert bar.security_id == security.id


# --- uniqueness ---


def test_duplicate_symbol_is_rejected(db_session) -> None:
    db_session.add(_make_security())
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_security())
        db_session.flush()

    assert _constraint_name(excinfo.value) == "uq_securities_symbol"


def test_duplicate_security_session_pair_is_rejected(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    db_session.add(_make_daily_price_bar(security.id))
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id))
        db_session.flush()

    assert _constraint_name(excinfo.value) == "uq_daily_price_bars_security_session"


# --- referential integrity ---


def test_foreign_key_violation_is_rejected(db_session) -> None:
    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security_id=-1))
        db_session.flush()

    assert _constraint_name(excinfo.value) == "daily_price_bars_security_id_fkey"


# --- OHLCV positivity ---


@pytest.mark.parametrize(
    ("column", "value", "constraint_name"),
    [
        pytest.param("low", Decimal(0), "ck_daily_price_bars_low_positive", id="low=0"),
        pytest.param("low", Decimal(-1), "ck_daily_price_bars_low_positive", id="low=-1"),
        pytest.param("close", Decimal(0), "ck_daily_price_bars_close_positive", id="close=0"),
        pytest.param("close", Decimal(-1), "ck_daily_price_bars_close_positive", id="close=-1"),
        # open<=0 and high<=0 are, under this schema, *also* necessarily a
        # relational violation: low_is_min requires low<=open, but low must
        # itself stay positive (low_positive), so low<=open can never hold
        # once open<=0 -- and symmetrically for high_is_max/high. Verified
        # empirically against real PostgreSQL: it reports the relational
        # constraint here, not open_positive/high_positive. Asserting that
        # real, exact name (rather than guessing open_positive/high_positive)
        # is the whole point of inspecting diagnostics instead of accepting
        # "any IntegrityError".
        pytest.param("open", Decimal(0), "ck_daily_price_bars_low_is_min", id="open=0"),
        pytest.param("open", Decimal(-1), "ck_daily_price_bars_low_is_min", id="open=-1"),
        pytest.param("high", Decimal(0), "ck_daily_price_bars_high_is_max", id="high=0"),
        pytest.param("high", Decimal(-1), "ck_daily_price_bars_high_is_max", id="high=-1"),
    ],
)
def test_nonpositive_price_is_rejected(db_session, column, value, constraint_name) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id, **{column: value}))
        db_session.flush()

    assert _constraint_name(excinfo.value) == constraint_name


# --- OHLC relational consistency ---


@pytest.mark.parametrize(
    ("overrides", "constraint_name"),
    [
        # high below open or close, while low stays the true minimum, so
        # low_is_min is untouched -- isolates high_is_max cleanly.
        pytest.param(
            {"open": Decimal(100), "high": Decimal(95), "low": Decimal(80), "close": Decimal(90)},
            "ck_daily_price_bars_high_is_max",
            id="high<open",
        ),
        pytest.param(
            {"open": Decimal(100), "high": Decimal(95), "low": Decimal(80), "close": Decimal(110)},
            "ck_daily_price_bars_high_is_max",
            id="high<close",
        ),
        # low above open or close, while high stays the true maximum, so
        # high_is_max is untouched -- isolates low_is_min cleanly.
        pytest.param(
            {"open": Decimal(80), "high": Decimal(120), "low": Decimal(100), "close": Decimal(110)},
            "ck_daily_price_bars_low_is_min",
            id="low>open",
        ),
        pytest.param(
            {"open": Decimal(110), "high": Decimal(120), "low": Decimal(100), "close": Decimal(90)},
            "ck_daily_price_bars_low_is_min",
            id="low>close",
        ),
        # Deliberately excluded: high<low. Both constraints restate the same
        # fact (high>=low / low<=high), so that case always trips both at
        # once and cannot be isolated to a single named constraint.
    ],
)
def test_invalid_high_low_relationship_is_rejected(db_session, overrides, constraint_name) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id, **overrides))
        db_session.flush()

    assert _constraint_name(excinfo.value) == constraint_name


# --- volume, provider, feed ---


def test_negative_volume_is_rejected(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id, volume=-1))
        db_session.flush()

    assert _constraint_name(excinfo.value) == "ck_daily_price_bars_volume_nonnegative"


def test_invalid_data_provider_is_rejected(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id, data_provider="other_vendor"))
        db_session.flush()

    assert _constraint_name(excinfo.value) == "ck_daily_price_bars_data_provider_alpaca"


def test_invalid_feed_is_rejected(db_session) -> None:
    security = _make_security()
    db_session.add(security)
    db_session.flush()

    with pytest.raises(IntegrityError) as excinfo, db_session.begin_nested():
        db_session.add(_make_daily_price_bar(security.id, feed="sip"))
        db_session.flush()

    assert _constraint_name(excinfo.value) == "ck_daily_price_bars_feed_iex"
