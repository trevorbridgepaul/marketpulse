"""Tests for the Alembic downgrade-on-dev safeguard.

Split in two groups:
- Unit tests exercise `reject_downgrade_step` and
  `on_version_apply_callbacks_for_target` directly, with no database, using
  minimal duck-typed step objects (only `is_migration`/`is_upgrade` are
  ever read by the callback).
- One integration test proves the safeguard's actual effect -- a rejected
  step rolls back its DDL and leaves the recorded revision unchanged --
  against the dedicated test database, using a synthetic, throwaway
  migration script isolated from the project's real `alembic/versions/`
  and its `alembic_version` table (via a distinct `version_table` name),
  so it never touches the real schema or depends on its current revision.
"""

from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db_migration_safety import (
    DowngradeRejected,
    on_version_apply_callbacks_for_target,
    reject_downgrade_step,
)

# --- unit tests: callback and target-selection logic, no database ---


def test_upgrade_step_is_allowed() -> None:
    step = SimpleNamespace(is_migration=True, is_upgrade=True)

    reject_downgrade_step(ctx=None, step=step, heads=(), run_args={})


def test_downgrade_step_is_rejected() -> None:
    step = SimpleNamespace(is_migration=True, is_upgrade=False)

    with pytest.raises(DowngradeRejected):
        reject_downgrade_step(ctx=None, step=step, heads=(), run_args={})


def test_stamp_step_is_recognized_and_not_treated_as_a_downgrade() -> None:
    """A `stamp` step carries is_migration=False and runs no DDL at all --
    it must never be mistaken for an ordinary downgrade migration here."""
    step = SimpleNamespace(is_migration=False, is_upgrade=False)

    reject_downgrade_step(ctx=None, step=step, heads=(), run_args={})


def test_dev_target_installs_the_downgrade_guard() -> None:
    assert on_version_apply_callbacks_for_target("dev") == (reject_downgrade_step,)


def test_test_target_installs_no_callback() -> None:
    assert on_version_apply_callbacks_for_target("test") == ()


# --- integration test: real rollback behavior on the test database ---

_PROBE_TABLE = "migration_safety_probe"
_PROBE_VERSION_TABLE = "migration_safety_probe_version"

_PROBE_REVISION_SOURCE = f'''
revision = "probe_rev"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table("{_PROBE_TABLE}", sa.Column("id", sa.Integer(), primary_key=True))


def downgrade():
    op.drop_table("{_PROBE_TABLE}")
'''


@pytest.fixture
def probe_script_directory(tmp_path):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()
    (versions_dir / "probe_rev.py").write_text(_PROBE_REVISION_SOURCE)

    config = Config()
    config.set_main_option("script_location", str(tmp_path))
    return config, ScriptDirectory.from_config(config)


def _run(test_engine, config, script, *, fn, destination_rev, on_version_apply=()):
    env_context = EnvironmentContext(config, script, fn=fn, destination_rev=destination_rev)
    with test_engine.connect() as connection:
        env_context.configure(
            connection=connection,
            version_table=_PROBE_VERSION_TABLE,
            on_version_apply=on_version_apply,
        )
        with env_context.begin_transaction():
            env_context.run_migrations()


def test_rejected_downgrade_rolls_back_without_persisting_or_changing_revision(
    test_engine, probe_script_directory
) -> None:
    config, script = probe_script_directory

    def _upgrade(rev, context):
        return script._upgrade_revs("head", rev)

    def _downgrade(rev, context):
        return script._downgrade_revs("base", rev)

    try:
        _run(test_engine, config, script, fn=_upgrade, destination_rev="head")

        with test_engine.connect() as connection:
            assert inspect(connection).has_table(_PROBE_TABLE)
            recorded_revision = connection.execute(
                text(f"SELECT version_num FROM {_PROBE_VERSION_TABLE}")
            ).scalar_one()
            assert recorded_revision == "probe_rev"

        with pytest.raises(DowngradeRejected):
            _run(
                test_engine,
                config,
                script,
                fn=_downgrade,
                destination_rev="base",
                on_version_apply=(reject_downgrade_step,),
            )

        with test_engine.connect() as connection:
            assert inspect(connection).has_table(_PROBE_TABLE), (
                "the rejected downgrade's DDL must have been rolled back"
            )
            recorded_revision = connection.execute(
                text(f"SELECT version_num FROM {_PROBE_VERSION_TABLE}")
            ).scalar_one()
            assert recorded_revision == "probe_rev", (
                "the recorded revision must be unchanged by the rejected downgrade"
            )
    finally:
        _run(test_engine, config, script, fn=_downgrade, destination_rev="base")
        with test_engine.connect() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {_PROBE_VERSION_TABLE}"))
            connection.commit()
