"""Durable registration and participation notices after synchronization."""

import sqlalchemy as sa

from alembic import op

revision = "0004_open_notices"
down_revision = "0003_multi_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "notify_open_events" not in {
        column["name"] for column in inspector.get_columns("user_profiles")
    }:
        op.add_column(
            "user_profiles",
            sa.Column("notify_open_events", sa.Boolean(), nullable=False, server_default="1"),
        )
    if "open_event_notices" not in inspector.get_table_names():
        op.create_table(
            "open_event_notices",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
            sa.Column("event_id", sa.String(120), nullable=False),
            sa.Column("milestone_id", sa.String(160), nullable=True),
            sa.Column("phase", sa.String(180), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "telegram_user_id", "event_id", "phase", name="uq_open_event_notice"
            ),
        )
        op.create_index(
            "ix_open_notice_pending",
            "open_event_notices",
            ["telegram_user_id", "status", "next_attempt_at"],
        )


def downgrade() -> None:
    op.drop_table("open_event_notices")
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("notify_open_events")
