from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine)


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] = SessionLocal,
) -> Generator[Session, None, None]:
    """Yield a Session. The caller owns the transaction boundary.

    This does NOT commit automatically. The calling application/service
    code is responsible for calling `session.commit()` after a
    successful write. If the block exits normally without an explicit
    commit, any uncommitted changes are rolled back (silently, not as
    an error) when the session closes -- this is deliberate: it keeps
    control over what constitutes one atomic unit of work with the
    caller (e.g. a repository method importing several related rows in
    one transaction), rather than committing after every statement.

    On an exception, the session is explicitly rolled back before the
    exception is re-raised. In every case -- success, explicit commit,
    or exception -- the session is closed and its connection returned
    to the pool.
    """
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> AbstractContextManager[Session]:
    """Entry point for `with get_session() as session: ...` against the
    primary (non-test) database.

    Follows the same caller-owns-commit contract as `session_scope`:
    call `session.commit()` yourself after a successful write, or it
    will be rolled back when the session closes.
    """
    return session_scope()
