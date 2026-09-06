"""Initial OlymPing schema.

Revision ID: 0001_ux_schema
Revises:
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_ux_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(120)),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("format", sa.String(100)),
        sa.Column("location", sa.String(300)),
        sa.Column("is_online", sa.Boolean()),
        sa.Column("restrictions", sa.String(100)),
        sa.Column("weight", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_kind", "external_id", name="uq_event_source_external"),
    )
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_source_kind", "events", ["source_kind"])
    op.create_index("ix_events_status_kind", "events", ["status", "source_kind"])

    op.create_table(
        "user_profiles",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("category_settings", sa.JSON(), nullable=False),
        sa.Column("ctf_filters", sa.JSON(), nullable=False),
        sa.Column("notify_new_events", sa.Boolean(), nullable=False),
        sa.Column("auto_subscribe_new_events", sa.Boolean(), nullable=False),
        sa.Column("notify_event_updates", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "milestones",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("precision", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("format", sa.String(100)),
        sa.Column("location", sa.String(300)),
        sa.Column("is_online", sa.Boolean()),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_milestones_due", "milestones", ["status", "starts_at"])
    op.create_index("ix_milestones_event_id", "milestones", ["event_id"])
    op.create_index("ix_milestones_kind", "milestones", ["kind"])

    op.create_table(
        "reminder_rules",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(20)),
        sa.Column("event_id", sa.String(120)),
        sa.Column("milestone_kind", sa.String(40)),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("offset_minutes", sa.Integer()),
        sa.Column("days_before", sa.Integer()),
        sa.Column("local_time", sa.String(5)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_reminder_rules_event_id", "reminder_rules", ["event_id"])
    op.create_index("ix_reminder_rules_telegram_user_id", "reminder_rules", ["telegram_user_id"])
    op.create_index(
        "ix_rule_scope", "reminder_rules", ["telegram_user_id", "source_kind", "event_id"]
    )

    op.create_table(
        "event_preferences",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("interest", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("telegram_user_id", "event_id"),
    )

    op.create_table(
        "stage_progress",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("milestone_id", sa.String(160), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("telegram_user_id", "milestone_id"),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("milestone_id", sa.String(160), nullable=False),
        sa.Column("reminder_rule_id", sa.String(120), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reminder_rule_id"], ["reminder_rules.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "telegram_user_id",
            "milestone_id",
            "reminder_rule_id",
            "scheduled_for",
            name="uq_delivery_occurrence",
        ),
    )
    op.create_index("ix_delivery_pending", "notification_deliveries", ["status", "scheduled_for"])
    op.create_index(
        "ix_notification_deliveries_milestone_id", "notification_deliveries", ["milestone_id"]
    )
    op.create_index(
        "ix_notification_deliveries_telegram_user_id",
        "notification_deliveries",
        ["telegram_user_id"],
    )

    op.create_table(
        "catalog_notices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("milestone_id", sa.String(160)),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["milestone_id"], ["milestones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["telegram_user_id"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_catalog_notice_unsent", "catalog_notices", ["telegram_user_id", "sent_at", "created_at"]
    )
    op.create_index("ix_catalog_notices_telegram_user_id", "catalog_notices", ["telegram_user_id"])

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("success", sa.Boolean()),
        sa.Column("details", sa.Text(), nullable=False),
    )
    op.create_index("ix_sync_runs_source", "sync_runs", ["source"])


def downgrade() -> None:
    op.drop_table("catalog_notices")
    op.drop_table("notification_deliveries")
    op.drop_table("stage_progress")
    op.drop_table("event_preferences")
    op.drop_table("reminder_rules")
    op.drop_table("milestones")
    op.drop_table("sync_runs")
    op.drop_table("user_profiles")
    op.drop_table("events")
