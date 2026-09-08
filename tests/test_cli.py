import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from olymping.cli import _with_database  # pyright: ignore[reportPrivateUsage]
from olymping.config import Settings
from olymping.db import create_engine, create_session_factory
from olymping.models import Event
from olymping.services.importer import CalendarImportError, calendar_paths, import_data_directory


def test_cli_import_does_not_load_bot_or_orm() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import olymping.cli; "
            "assert 'aiogram' not in sys.modules; assert 'sqlalchemy' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_health_probe_does_not_create_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    settings = Settings(database_url=f"sqlite+aiosqlite:///{path}")
    with pytest.raises(sqlite3.OperationalError):
        await _with_database(settings, "healthcheck")
    assert not path.exists()


def test_calendar_paths_rejects_missing_and_empty_directories(tmp_path: Path) -> None:
    with pytest.raises(CalendarImportError, match="does not exist"):
        calendar_paths(tmp_path / "missing")
    with pytest.raises(CalendarImportError, match="no YAML"):
        calendar_paths(tmp_path)
    path = tmp_path / "calendar.yml"
    path.write_text("calendar_version: 1\nevents: []\n")
    assert calendar_paths(tmp_path) == [path]


@pytest.mark.asyncio
async def test_cli_migrates_checks_and_imports_calendar(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}",
        owner_telegram_id=0,
        data_dir=Path("data/calendar"),
    )
    for command in ("db-upgrade", "doctor", "import-data", "healthcheck", "db-upgrade"):
        await _with_database(settings, command)
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            count = await session.scalar(select(func.count()).select_from(Event))
            assert count is not None and count > 0
            summary = await import_data_directory(session, settings.data_dir)
            assert summary.created_events == 0
            assert summary.updated_events == 0
            assert summary.created_milestones == 0
            assert summary.updated_milestones == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_doctor_validates_yml_files(tmp_path: Path) -> None:
    calendar = tmp_path / "calendar"
    calendar.mkdir()
    (calendar / "invalid.yml").write_text("calendar_version: 2\nevents: []\n")
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'doctor.db'}",
        owner_telegram_id=0,
        data_dir=calendar,
    )
    with pytest.raises(CalendarImportError, match="invalid calendar"):
        await _with_database(settings, "doctor")
