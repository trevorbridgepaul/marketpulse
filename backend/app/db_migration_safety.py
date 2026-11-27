"""Pure, unit-testable logic backing alembic/env.py's downgrade safeguard.

Kept out of env.py itself because env.py is executed as a standalone script
by Alembic's loader on every invocation (its module-level code always runs,
including the final run_migrations_online() call) -- there is no way to
import env.py in a test without that side effect. This module has none.
"""

from collections.abc import Callable, Sequence
from typing import Any


class DowngradeRejected(RuntimeError):
    """Raised by reject_downgrade_step when a downgrade step is detected."""


def reject_downgrade_step(**kwargs: Any) -> None:
    """on_version_apply callback: reject this step if it is a downgrade.

    A step is a downgrade when it is an ordinary migration step (not a
    `stamp` operation) moving backward through the revision graph, i.e.
    `step.is_migration` is True and `step.is_upgrade` is False.

    `stamp` operations (`step.is_migration` is False) are deliberately left
    alone here -- they run no upgrade()/downgrade() DDL at all, so there is
    nothing for a downgrade guard to meaningfully act on. A `stamp` moving
    the recorded revision backward on target=dev is a real, separate risk
    this callback does not cover -- see env.py's module docstring notes.
    """
    step = kwargs["step"]
    if step.is_migration and not step.is_upgrade:
        raise DowngradeRejected(
            "Refusing to apply a downgrade step against target=dev, "
            "regardless of how Alembic was invoked."
        )


def on_version_apply_callbacks_for_target(
    target: str,
) -> Sequence[Callable[..., None]]:
    """The on_version_apply callbacks to install for a given -x target.

    Only target=dev gets the downgrade guard. target=test must remain free
    to downgrade -- it is the dedicated database this project uses to
    verify upgrade/downgrade round-trips safely.
    """
    if target == "dev":
        return (reject_downgrade_step,)
    return ()
