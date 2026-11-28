from logging.config import fileConfig

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from alembic import context
from app.config import get_settings
from app.db_migration_safety import on_version_apply_callbacks_for_target
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# app.models.__init__ imports Security and DailyPriceBar, which registers
# both tables on Base.metadata -- that import is what makes them visible
# to autogenerate below.
target_metadata = Base.metadata

_SUPPORTED_TARGETS = ("dev", "test")


def _resolve_target_url() -> tuple[str, URL]:
    """Resolve the -x target=dev|test argument to a database URL.

    There is no default: a missing or unrecognized target is a hard error,
    so a migration can never run against the wrong database by omission.
    """
    x_args = context.get_x_argument(as_dictionary=True)
    target = x_args.get("target")

    if target not in _SUPPORTED_TARGETS:
        raise RuntimeError(
            f"Missing or unsupported -x target argument: {target!r}. "
            f"Pass one of -x target={{{'|'.join(_SUPPORTED_TARGETS)}}} explicitly, "
            "e.g. `alembic -x target=test upgrade head`."
        )

    settings = get_settings()
    if target == "test":
        return target, settings.test_database_url
    return target, settings.database_url


def _is_downgrade_command() -> bool:
    """Detect a `downgrade` invocation from the Alembic CLI's parsed command.

    This is the first of two independent downgrade-on-dev guards. It only
    sees commands run through the `alembic` console script, which sets
    config.cmd_opts.cmd to (command_function, ...) -- it canNOT see a
    downgrade triggered by calling alembic.command.downgrade(...) directly
    from Python without going through CLI argument parsing, since that path
    leaves cmd_opts unset. Kept because it fails fast, before any database
    connection is made, for the CLI invocation path used here and in CI.

    The second guard, registered below via on_version_apply_callbacks_for_target()
    in run_migrations_online(), is invocation-path-agnostic: it is driven by
    Alembic's own revision-graph traversal direction (step.is_upgrade), not
    by how Alembic was invoked, so it also catches a downgrade against
    target=dev triggered programmatically rather than through this CLI.
    """
    cmd_opts = getattr(config, "cmd_opts", None)
    cmd = getattr(cmd_opts, "cmd", None) if cmd_opts is not None else None
    return bool(cmd) and getattr(cmd[0], "__name__", None) == "downgrade"


def run_migrations_offline() -> None:
    raise RuntimeError(
        "Offline migrations (SQL-script generation without a live connection) "
        "are not supported in this project. Run against a real database with "
        "-x target=dev or -x target=test."
    )


def run_migrations_online() -> None:
    target, db_url = _resolve_target_url()

    if target == "dev" and _is_downgrade_command():
        raise RuntimeError(
            "Refusing to run `downgrade` against the development database "
            "(target=dev). Downgrades are only permitted against target=test."
        )

    # pool.NullPool-equivalent: a plain create_engine() here already opens
    # a single short-lived connection for this one migration run rather than
    # maintaining a pool, since this process exits right after.
    engine = create_engine(db_url)

    try:
        with engine.connect() as connection:
            connected_database = connection.execute(text("SELECT current_database()")).scalar_one()
            expected_database = db_url.database

            if connected_database != expected_database:
                raise RuntimeError(
                    "Refusing to run migrations: connected to database "
                    f"{connected_database!r}, but target={target!r} expected "
                    f"{expected_database!r}. This guard exists to stop a "
                    "misconfigured environment from migrating the wrong database."
                )

            # Never log the URL itself -- it carries the password. Only the
            # already-verified database name, host, and port are safe to print.
            print(
                f"alembic: running migrations against target={target!r} "
                f"database={connected_database!r} host={db_url.host!r} port={db_url.port!r}"
            )

            # The verification query above auto-began an implicit transaction
            # (SQLAlchemy 2.0 "autobegin"). If that transaction is still open
            # when context.configure() runs, Alembic treats this connection as
            # having an externally-managed transaction and will not commit it
            # itself -- silently rolling back the whole migration (including
            # alembic_version) when the connection closes. Ending it here
            # (safe: nothing but a read happened) lets Alembic own and commit
            # its own transaction as it normally would.
            connection.rollback()

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                on_version_apply=on_version_apply_callbacks_for_target(target),
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
