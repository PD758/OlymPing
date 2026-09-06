"""Require administrator review before catalog and availability broadcasts."""

import sqlalchemy as sa

from alembic import op

revision = "0005_notification_review"
down_revision = "0004_open_notices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_selections",
        sa.Column("review_batch_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("review_batch_id", "event_id"),
        sa.ForeignKeyConstraint(
            ["review_batch_id"], ["notification_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )
    for table in ("catalog_notices", "open_event_notices"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("review_batch_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_review", "notification_reviews", ["review_batch_id"], ["id"]
            )
        op.create_index(f"ix_{table}_review_batch_id", table, ["review_batch_id"])
    op.create_table(
        "review_deliveries",
        sa.Column("review_batch_id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_batch_id"], ["notification_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("review_deliveries")
    for table in ("catalog_notices", "open_event_notices"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_review_batch_id")
            batch.drop_constraint(f"fk_{table}_review", type_="foreignkey")
            batch.drop_column("review_batch_id")
    op.drop_table("review_selections")
    op.drop_table("notification_reviews")
