"""restrict notificationtype to BR-018 events

Revision ID: b3db1d04fec6
Revises: c41a0bbd3d85
Create Date: 2026-10-07 04:26:35.624421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3db1d04fec6'
down_revision: Union[str, Sequence[str], None] = 'c41a0bbd3d85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Postgres can't drop values from an enum type, so swap in a new type.
# Hand-written: autogenerate does not detect enum value changes.

NEW = ("request_received", "request_accepted", "request_declined")
OLD = NEW + ("account_approved", "account_rejected")


def _swap(values: tuple[str, ...]) -> None:
    op.execute("ALTER TYPE notificationtype RENAME TO notificationtype_old")
    sa.Enum(*values, name="notificationtype").create(op.get_bind())
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN type TYPE notificationtype "
        "USING type::text::notificationtype"
    )
    op.execute("DROP TYPE notificationtype_old")


def upgrade() -> None:
    # Any rows using the removed values would make the cast fail; there should be none.
    op.execute("DELETE FROM notifications WHERE type::text IN ('account_approved', 'account_rejected')")
    _swap(NEW)


def downgrade() -> None:
    _swap(OLD)
