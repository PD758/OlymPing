"""Track subscription origin, progression and durable workflow notifications."""

import sqlalchemy as sa

from alembic import op

revision = "0006_progression_subscriptions"
down_revision = "0005_notification_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_preferences",
        sa.Column(
            "origin",
            sa.String(20),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column("milestones", sa.Column("results_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("milestones", sa.Column("advancement_paths", sa.JSON(), nullable=True))
    op.add_column("milestones", sa.Column("terminal", sa.Boolean(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE milestones SET terminal = 1, advancement_paths = '[]' "
            "WHERE event_id LIKE 'ctftime:%' AND kind = 'competition'"
        )
    )
    op.create_table(
        "workflow_notices",
        sa.Column("key", sa.String(220), primary_key=True),
        sa.Column(
            "telegram_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "milestone_id",
            sa.String(160),
            sa.ForeignKey("milestones.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_notices")
    for column in ("terminal", "advancement_paths", "results_at"):
        op.drop_column("milestones", column)
    op.drop_column("event_preferences", "origin")
