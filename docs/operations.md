# Operations

Run one OlymPing instance for this SQLite deployment. A second bot process can
poll Telegram at the same time and can contend for the database.

## Start and check

Create the host backup directory with the container UID/GID, then start the
services. The setup command requires host-root privileges only to assign the
narrow directory ownership:

```sh
sudo ./scripts/setup-backups.sh
docker compose up -d --build
docker compose ps
```

The `backup` sidecar makes a verified SQLite online backup immediately when the
database exists, then once every 24 hours. Backups are timestamped `.db` files
in `./backups`, which is deliberately a bind mount outside the Docker database
volume. It retains the newest 14 files. The sidecar health check fails if no
backup is newer than 26 hours.

The bind mount is still local to the host. Copy `./backups` to storage outside
that host on a schedule appropriate for the data-loss window you accept; a
local backup does not protect against host loss.

Check a backup before copying or restoring it:

```sh
docker compose run --rm --no-deps backup \
  python -m olymping.services.backups verify --path /backups/olymping-YYYYMMDDTHHMMSSZ.db
```

## Restore

Restoration must happen with the bot stopped, so it cannot poll Telegram or
write SQLite during replacement. This also avoids two bot instances when the
replacement starts.

```sh
docker compose stop bot backup
docker compose run --rm --no-deps \
  -v ./backups:/backups:ro \
  bot python -m olymping.services.backups restore \
  --database-url sqlite+aiosqlite:////app/data/olymping.db \
  --path /backups/olymping-YYYYMMDDTHHMMSSZ.db \
  --service-stopped
docker compose up -d bot backup
```

The restore command rejects an invalid candidate, writes and integrity-checks a
replacement first, and keeps the original as `olymping.db.before-restore-*`.
After startup, confirm `docker compose ps` shows both services healthy and use
the bot's normal calendar view to check expected data.

If the restored database is incompatible with the running release or the check
fails, stop both services again and restore the retained
`olymping.db.before-restore-*` file using the same command. Use a backup made
by a compatible release when rolling back application schema; migrations are
applied when the bot starts.
