from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from olymping.services.backups import BackupError, backup_database, backup_fresh, restore_database


def create_database(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE values_table (value TEXT NOT NULL)")
        connection.execute("INSERT INTO values_table VALUES (?)", (value,))


def value_in(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return str(connection.execute("SELECT value FROM values_table").fetchone()[0])


def test_online_backup_is_verified_and_retained(tmp_path: Path) -> None:
    database = tmp_path / "olymping.db"
    backups = tmp_path / "backups"
    create_database(database, "original")

    first = backup_database(database, backups, retention_count=1)
    assert value_in(first) == "original"
    assert backup_fresh(backups, max_age_hours=1)

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE values_table SET value = 'newer'")
    second = backup_database(database, backups, retention_count=1)

    assert second.exists()
    assert value_in(second) == "newer"
    assert list(backups.glob("olymping-*.db")) == [second]


def test_online_backup_reads_uncheckpointed_wal_data(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    database_dir.mkdir()
    database = database_dir / "olymping.db"
    backups = tmp_path / "backups"
    create_database(database, "before")

    with sqlite3.connect(database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE values_table SET value = 'in wal'")
        writer.commit()
        os.chmod(database_dir, 0o555)
        try:
            copied = backup_database(database, backups, retention_count=14)
        finally:
            os.chmod(database_dir, 0o755)

    assert value_in(copied) == "in wal"


def test_restore_requires_stopped_service_and_keeps_previous_database(tmp_path: Path) -> None:
    database = tmp_path / "olymping.db"
    candidate = tmp_path / "candidate.db"
    create_database(database, "live")
    create_database(candidate, "backup")

    with pytest.raises(BackupError, match="service-stopped"):
        restore_database(database, candidate, service_stopped=False)

    previous = restore_database(database, candidate, service_stopped=True)
    assert value_in(database) == "backup"
    assert value_in(previous) == "live"


def test_restore_checkpoints_original_wal_and_removes_old_companions(tmp_path: Path) -> None:
    database = tmp_path / "olymping.db"
    candidate = tmp_path / "candidate.db"
    create_database(database, "old")
    create_database(candidate, "candidate")

    with sqlite3.connect(database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE values_table SET value = 'old wal'")
        writer.commit()
        assert Path(f"{database}-wal").exists()
        previous = restore_database(database, candidate, service_stopped=True)

    assert value_in(database) == "candidate"
    assert value_in(previous) == "old wal"
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()


def test_restore_rejects_active_writer(tmp_path: Path) -> None:
    database = tmp_path / "olymping.db"
    candidate = tmp_path / "candidate.db"
    create_database(database, "live")
    create_database(candidate, "candidate")

    with sqlite3.connect(database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("UPDATE values_table SET value = 'pending'")
        with pytest.raises(BackupError, match="busy"):
            restore_database(database, candidate, service_stopped=True)
        writer.rollback()

    assert value_in(database) == "live"


def test_restore_rejects_corrupt_candidate_without_touching_live_database(tmp_path: Path) -> None:
    database = tmp_path / "olymping.db"
    candidate = tmp_path / "broken.db"
    create_database(database, "live")
    candidate.write_bytes(b"not sqlite")

    with pytest.raises(BackupError, match="SQLite"):
        restore_database(database, candidate, service_stopped=True)
    assert value_in(database) == "live"
