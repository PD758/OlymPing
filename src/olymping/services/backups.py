"""Small, dependency-free SQLite backup and restore utility.

The backup command uses SQLite's online backup API, so it can copy a WAL-mode
database while the bot is reading and writing it.  Restore is deliberately a
manual, stopped-service operation.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_RETENTION_COUNT = 14


class BackupError(RuntimeError):
    """Raised when a backup or restore cannot be safely completed."""


def sqlite_path(database_url: str) -> Path:
    """Return the filesystem path for a local SQLAlchemy SQLite URL."""
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            raw_path = database_url.removeprefix(prefix)
            if raw_path and raw_path != ":memory:" and not raw_path.startswith("file:"):
                return Path(raw_path).expanduser().resolve()
    raise BackupError("only filesystem SQLite database URLs are supported")


def _sqlite_uri(path: Path, *, read_only: bool = False) -> str:
    suffix = "?mode=ro" if read_only else ""
    return path.resolve().as_uri() + suffix


def verify_database(path: Path) -> None:
    """Raise BackupError unless *path* is a readable, internally consistent SQLite DB."""
    if not path.is_file():
        raise BackupError(f"database file does not exist: {path}")
    try:
        with closing(sqlite3.connect(_sqlite_uri(path, read_only=True), uri=True)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"cannot read SQLite database {path}: {exc}") from exc
    if result != ("ok",):
        raise BackupError(f"SQLite integrity check failed for {path}: {result!r}")


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def backup_database(database: Path, backup_dir: Path, retention_count: int) -> Path:
    """Create a verified, timestamped online backup and apply bounded retention."""
    if retention_count < 1:
        raise BackupError("retention count must be at least one")
    if not database.is_file():
        raise BackupError(f"database file does not exist: {database}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"olymping-{timestamp}.db"
    temporary = backup_dir / f".{destination.name}.tmp-{os.getpid()}"
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with (
            closing(sqlite3.connect(_sqlite_uri(database, read_only=True), uri=True)) as source,
            closing(sqlite3.connect(_sqlite_uri(temporary), uri=True)) as target,
        ):
            source.backup(target)
        verify_database(temporary)
        _fsync_file(temporary)
        os.replace(temporary, destination)
        _fsync_directory(backup_dir)
    except (OSError, sqlite3.Error) as exc:
        raise BackupError(f"could not create backup: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    _apply_retention(backup_dir, retention_count)
    return destination


def _apply_retention(backup_dir: Path, retention_count: int) -> None:
    backups = sorted(
        backup_dir.glob("olymping-*.db"), key=lambda item: item.stat().st_mtime_ns, reverse=True
    )
    for stale in backups[retention_count:]:
        stale.unlink()
    if len(backups) > retention_count:
        _fsync_directory(backup_dir)


def _checkpoint_and_lock(database: Path) -> None:
    """Reject active writers and fold any WAL data into the original database."""
    try:
        with closing(sqlite3.connect(_sqlite_uri(database), uri=True)) as connection:
            connection.execute("PRAGMA busy_timeout = 0")
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is None or checkpoint[0] != 0:
                raise BackupError("database is busy; stop the bot and all SQLite writers first")
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute("ROLLBACK")
    except sqlite3.Error as exc:
        raise BackupError("database is busy; stop the bot and all SQLite writers first") from exc


def _companion_paths(database: Path) -> tuple[Path, Path]:
    return (Path(f"{database}-wal"), Path(f"{database}-shm"))


def restore_database(database: Path, candidate: Path, *, service_stopped: bool) -> Path:
    """Replace a stopped service's database with a pre-verified candidate.

    The original is moved aside only after the candidate has been copied and
    checked in the database filesystem, so an operator can roll back manually.
    """
    if not service_stopped:
        raise BackupError("restore requires --service-stopped; stop the bot before restoring")
    verify_database(candidate)
    database.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    replacement = database.with_name(f".{database.name}.restore-{os.getpid()}")
    previous = database.with_name(f"{database.name}.before-restore-{timestamp}")
    try:
        shutil.copy2(candidate, replacement)
        replacement.chmod(0o600)
        verify_database(replacement)
        _fsync_file(replacement)
        if database.exists():
            _checkpoint_and_lock(database)
            os.replace(database, previous)
            for companion in _companion_paths(database):
                companion.unlink(missing_ok=True)
        os.replace(replacement, database)
        _fsync_directory(database.parent)
        verify_database(database)
    except (OSError, sqlite3.Error) as exc:
        raise BackupError(f"could not restore database: {exc}") from exc
    finally:
        replacement.unlink(missing_ok=True)
    return previous


def backup_fresh(backup_dir: Path, max_age_hours: int) -> bool:
    newest = max(
        backup_dir.glob("olymping-*.db"), default=None, key=lambda item: item.stat().st_mtime
    )
    if newest is None:
        return False
    try:
        verify_database(newest)
    except BackupError:
        return False
    age = datetime.now(UTC) - datetime.fromtimestamp(newest.stat().st_mtime, UTC)
    return age <= timedelta(hours=max_age_hours)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m olymping.services.backups")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("backup", "loop"):
        command = subparsers.add_parser(name)
        command.add_argument("--database-url", required=True)
        command.add_argument("--backup-dir", type=Path, required=True)
        command.add_argument("--retention-count", type=int, default=DEFAULT_RETENTION_COUNT)
        if name == "loop":
            command.add_argument("--interval-hours", type=float, default=24)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--path", type=Path, required=True)
    fresh = subparsers.add_parser("fresh")
    fresh.add_argument("--backup-dir", type=Path, required=True)
    fresh.add_argument("--max-age-hours", type=int, default=26)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--database-url", required=True)
    restore.add_argument("--path", type=Path, required=True)
    restore.add_argument("--service-stopped", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "backup":
            database = sqlite_path(args.database_url)
            print(backup_database(database, args.backup_dir, args.retention_count))
        elif args.command == "loop":
            if args.interval_hours <= 0:
                raise BackupError("interval must be positive")
            while True:
                database = sqlite_path(args.database_url)
                if database.exists():
                    print(
                        backup_database(database, args.backup_dir, args.retention_count), flush=True
                    )
                else:
                    # A fresh deployment may create its database after this
                    # sidecar starts; retry promptly for the first backup.
                    time.sleep(min(60, args.interval_hours * 3600))
                    continue
                time.sleep(args.interval_hours * 3600)
        elif args.command == "verify":
            verify_database(args.path)
            print("OK")
        elif args.command == "fresh":
            if not backup_fresh(args.backup_dir, args.max_age_hours):
                raise BackupError("no recent verified backup")
            print("OK")
        else:
            previous = restore_database(
                sqlite_path(args.database_url), args.path, service_stopped=args.service_stopped
            )
            print(f"restored; previous database retained at {previous}")
    except BackupError as exc:
        print(f"backup error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
