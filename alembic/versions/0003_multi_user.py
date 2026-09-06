"""Add multi-user access and invitations.

Revision ID: 0003_multi_user
Revises: 0002_catalog_filters
Create Date: 2026-09-02
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_multi_user"
down_revision = "0002_catalog_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_profiles")}
    additions = [
        ("role", sa.String(length=20), "user"),
        ("access_status", sa.String(length=20), "active"),
        ("onboarding_completed", sa.Boolean(), "1"),
        ("username", sa.String(length=64), None),
        ("display_name", sa.String(length=200), None),
    ]
    for name, column_type, default in additions:
        if name in columns:
            continue
        op.add_column(
            "user_profiles",
            sa.Column(name, column_type, nullable=default is None, server_default=default),
        )
    indexes = {index["name"] for index in inspector.get_indexes("user_profiles")}
    if "ix_user_profiles_role" not in indexes:
        op.create_index("ix_user_profiles_role", "user_profiles", ["role"])
    if "ix_user_profiles_access_status" not in indexes:
        op.create_index("ix_user_profiles_access_status", "user_profiles", ["access_status"])
    if "invitations" not in inspector.get_table_names():
        op.create_table(
            "invitations",
            sa.Column("token", sa.String(length=64), primary_key=True),
            sa.Column("created_by", sa.BigInteger(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_by", sa.BigInteger(), nullable=True),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["created_by"], ["user_profiles.telegram_user_id"], ondelete="CASCADE"
            ),
        )
        op.create_index("ix_invitations_created_by", "invitations", ["created_by"])
        op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])


def downgrade() -> None:
    op.drop_table("invitations")
    with op.batch_alter_table("user_profiles") as batch:
        batch.drop_index("ix_user_profiles_access_status")
        batch.drop_index("ix_user_profiles_role")
        batch.drop_column("display_name")
        batch.drop_column("username")
        batch.drop_column("onboarding_completed")
        batch.drop_column("access_status")
        batch.drop_column("role")
