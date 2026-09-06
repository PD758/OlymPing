from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from sqlalchemy import text

from olymping.bot import run_bot
from olymping.config import Settings
from olymping.db import create_engine, create_session_factory, upgrade_schema
from olymping.services.ctftime import sync_ctftime
from olymping.services.importer import calendar_paths, import_data_directory, load_calendar_document
from olymping.services.runtime_health import check_runtime_health
from olymping.services.users import ensure_admin_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="olymping")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("bot", help="run the Telegram bot")
    import_parser = subparsers.add_parser("import-data", help="import YAML calendar data")
    import_parser.add_argument("path", nargs="?", type=Path)
    subparsers.add_parser("sync-ctftime", help="synchronize upcoming CTFtime events")
    subparsers.add_parser("db-upgrade", help="apply database migrations")
    subparsers.add_parser("doctor", help="validate configuration, data and database")
    health = subparsers.add_parser("healthcheck", help="check database and running bot workers")
    health.add_argument("--database-only", action="store_true", help="check an offline database")
    return parser


async def _with_database(settings: Settings, command: str, path: Path | None = None) -> None:
    if command != "healthcheck":
        await upgrade_schema(settings.database_url)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            if settings.owner_telegram_id > 0 and command != "healthcheck":
                await ensure_admin_profile(session, settings.owner_telegram_id, settings.timezone)
            if command == "healthcheck":
                await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                await session.execute(text("SELECT 1"))
                print("OK")
            elif command == "db-upgrade":
                print("Database is at the latest revision")
            elif command == "import-data":
                summary = await import_data_directory(session, path or settings.data_dir)
                print(summary)
            elif command == "sync-ctftime":
                summary = await sync_ctftime(
                    session,
                    base_url=settings.ctftime_base_url,
                    lookahead_days=settings.ctftime_lookahead_days,
                )
                print(summary)
            elif command == "doctor":
                for file_path in calendar_paths(settings.data_dir):
                    load_calendar_document(file_path)
                await session.execute(text("SELECT 1"))
                print(
                    f"OK: timezone={settings.timezone}, data={settings.data_dir}, "
                    "database reachable"
                )
            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    command = args.command or "bot"
    if command == "bot":
        asyncio.run(run_bot(settings))
    else:
        asyncio.run(_with_database(settings, command, getattr(args, "path", None)))
        if command == "healthcheck" and not args.database_only:
            health = asyncio.run(check_runtime_health(settings))
            if not health.healthy:
                parser.exit(1, f"Unhealthy: {health.reason}\n")
