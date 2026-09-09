from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from olymping.models import Base


def migration_config(database: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def sync_database_url(config: Config) -> str:
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None
    return url.replace("+aiosqlite", "")


def revision(connection: sa.Connection) -> str:
    return connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()


def test_initial_migration_is_frozen_before_later_catalog_and_user_fields(tmp_path: Path) -> None:
    config = migration_config(tmp_path / "initial.db")
    command.upgrade(config, "0001_ux_schema")

    engine = sa.create_engine(sync_database_url(config))
    try:
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names()) == {
            "alembic_version",
            "catalog_notices",
            "event_preferences",
            "events",
            "milestones",
            "notification_deliveries",
            "reminder_rules",
            "stage_progress",
            "sync_runs",
            "user_profiles",
        }
        assert {column["name"] for column in inspector.get_columns("events")} == {
            "category",
            "created_at",
            "description",
            "external_id",
            "format",
            "id",
            "is_online",
            "location",
            "restrictions",
            "source_checked_at",
            "source_kind",
            "source_url",
            "status",
            "tags",
            "title",
            "updated_at",
            "url",
            "weight",
        }
        assert {column["name"] for column in inspector.get_columns("user_profiles")} == {
            "auto_subscribe_new_events",
            "category_settings",
            "created_at",
            "ctf_filters",
            "notify_event_updates",
            "notify_new_events",
            "telegram_user_id",
            "timezone",
            "updated_at",
        }
        assert {index["name"] for index in inspector.get_indexes("events")} == {
            "ix_events_category",
            "ix_events_source_kind",
            "ix_events_status_kind",
        }
        event_unique_constraints = {
            constraint["name"] for constraint in inspector.get_unique_constraints("events")
        }
        assert event_unique_constraints == {"uq_event_source_external"}
    finally:
        engine.dispose()


def test_upgrade_from_multi_user_preserves_catalog_and_reminder_history(tmp_path: Path) -> None:
    config = migration_config(tmp_path / "upgrade.db")
    command.upgrade(config, "0003_multi_user")
    now = datetime(2026, 9, 6, tzinfo=UTC)
    timestamp = now.isoformat()

    engine = sa.create_engine(sync_database_url(config))
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO user_profiles (
                        telegram_user_id, role, access_status, onboarding_completed, username,
                        display_name, timezone, category_settings, ctf_filters, school_grade,
                        tag_filters, notify_new_events, auto_subscribe_new_events,
                        notify_event_updates, created_at, updated_at
                    ) VALUES (
                        :user_id, :role, :access_status, :onboarding_completed, :username,
                        :display_name, :timezone, :category_settings, :ctf_filters, :school_grade,
                        :tag_filters, :notify_new_events, :auto_subscribe_new_events,
                        :notify_event_updates, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "user_id": 101,
                    "role": "user",
                    "access_status": "active",
                    "onboarding_completed": True,
                    "username": "friend",
                    "display_name": "Friend",
                    "timezone": "Europe/Moscow",
                    "category_settings": json.dumps({"RSOSH": True}),
                    "ctf_filters": json.dumps({}),
                    "school_grade": 10,
                    "tag_filters": json.dumps(["informatics"]),
                    "notify_new_events": True,
                    "auto_subscribe_new_events": True,
                    "notify_event_updates": True,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO events (
                        id, source_kind, title, description, category, tags, source_url, status,
                        created_at, updated_at
                    ) VALUES (
                        :id, :source_kind, :title, :description, :category, :tags, :source_url,
                        :status, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "rsosh:migration-test",
                    "source_kind": "RSOSH",
                    "title": "Migration test",
                    "description": "",
                    "category": "informatics",
                    "tags": json.dumps(["rsosh"]),
                    "source_url": "https://example.edu/official",
                    "status": "confirmed",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO milestones (
                        id, event_id, kind, title, precision, status, created_at, updated_at
                    ) VALUES (
                        :id, :event_id, :kind, :title, :precision, :status, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "rsosh:migration-test:final",
                    "event_id": "rsosh:migration-test",
                    "kind": "final",
                    "title": "Final",
                    "precision": "unknown",
                    "status": "tbd",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO reminder_rules (
                        id, telegram_user_id, event_id, mode, enabled, created_at, updated_at
                    ) VALUES (
                        :id, :user_id, :event_id, :mode, :enabled, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "rule:migration-test",
                    "user_id": 101,
                    "event_id": "rsosh:migration-test",
                    "mode": "offset",
                    "enabled": True,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO event_preferences (
                        telegram_user_id, event_id, interest, created_at, updated_at
                    ) VALUES (:user_id, :event_id, :interest, :created_at, :updated_at)
                    """
                ),
                {
                    "user_id": 101,
                    "event_id": "rsosh:migration-test",
                    "interest": "watching",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog_notices (
                        telegram_user_id, event_id, milestone_id, kind, summary,
                        created_at, updated_at
                    ) VALUES (
                        :user_id, :event_id, :milestone_id, :kind, :summary,
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "user_id": 101,
                    "event_id": "rsosh:migration-test",
                    "milestone_id": "rsosh:migration-test:final",
                    "kind": "new_event",
                    "summary": "saved catalog history",
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO stage_progress "
                    "(telegram_user_id, milestone_id, outcome, created_at, updated_at) "
                    "VALUES (101, 'rsosh:migration-test:final', 'passed', :now, :now)"
                ),
                {"now": timestamp},
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = sa.create_engine(sync_database_url(config))
    try:
        with engine.connect() as connection:
            assert revision(connection) != "0003_multi_user"
            assert (
                connection.execute(
                    sa.text("SELECT username FROM user_profiles WHERE telegram_user_id = 101")
                ).scalar_one()
                == "friend"
            )
            assert (
                connection.execute(sa.text("SELECT interest FROM event_preferences")).scalar_one()
                == "watching"
            )
            assert (
                connection.execute(sa.text("SELECT origin FROM event_preferences")).scalar_one()
                == "manual"
            )
            assert (
                connection.execute(sa.text("SELECT results_at FROM milestones")).scalar_one()
                is None
            )
            assert (
                connection.execute(sa.text("SELECT advancement_paths FROM milestones")).scalar_one()
                is None
            )
            assert (
                connection.execute(sa.text("SELECT id FROM reminder_rules")).scalar_one()
                == "rule:migration-test"
            )
            assert (
                connection.execute(sa.text("SELECT summary FROM catalog_notices")).scalar_one()
                == "saved catalog history"
            )
            assert (
                connection.execute(sa.text("SELECT outcome FROM stage_progress")).scalar_one()
                == "passed"
            )
    finally:
        engine.dispose()


def test_downgrade_and_reupgrade_temporary_database(tmp_path: Path) -> None:
    config = migration_config(tmp_path / "round-trip.db")
    command.upgrade(config, "head")
    command.downgrade(config, "0002_catalog_filters")
    command.upgrade(config, "head")

    engine = sa.create_engine(sync_database_url(config))
    try:
        with engine.connect() as connection:
            assert revision(connection) != "0002_catalog_filters"
            assert "user_profiles" in sa.inspect(connection).get_table_names()
    finally:
        engine.dispose()


def test_migrations_converge_to_the_runtime_schema(tmp_path: Path) -> None:
    config = migration_config(tmp_path / "convergence.db")
    command.upgrade(config, "head")

    engine = sa.create_engine(sync_database_url(config))
    try:
        inspector = sa.inspect(engine)
        assert set(Base.metadata.tables) <= set(inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            assert {column.name for column in table.columns} == {
                column["name"] for column in inspector.get_columns(table.name)
            }
    finally:
        engine.dispose()
