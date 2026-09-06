"""Add grade and tag filters.

Revision ID: 0002_catalog_filters
Revises: 0001_ux_schema
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_catalog_filters"
down_revision = "0001_ux_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    event_columns = {column["name"] for column in inspector.get_columns("events")}
    if "min_grade" not in event_columns:
        op.add_column("events", sa.Column("min_grade", sa.Integer(), nullable=True))
    if "max_grade" not in event_columns:
        op.add_column("events", sa.Column("max_grade", sa.Integer(), nullable=True))
        op.create_index("ix_events_max_grade", "events", ["max_grade"])
    profile_columns = {column["name"] for column in inspector.get_columns("user_profiles")}
    if "school_grade" not in profile_columns:
        op.add_column("user_profiles", sa.Column("school_grade", sa.Integer(), nullable=True))
    if "tag_filters" not in profile_columns:
        op.add_column(
            "user_profiles",
            sa.Column("tag_filters", sa.JSON(), nullable=False, server_default="[]"),
        )
    op.execute("UPDATE user_profiles SET school_grade = 11 WHERE school_grade IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_column("tag_filters")
        batch.drop_column("school_grade")
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_max_grade")
        batch.drop_column("max_grade")
        batch.drop_column("min_grade")
