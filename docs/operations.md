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

## Calendar updates

Calendar-only changes do not bump the application version, Docker image tag or
`calendar_version` (which describes the YAML schema). Commit the reviewed YAML and
source notes as an ordinary data update. Bump the application release only when
changing application code, dependencies or deployment behavior.

Commit and push reviewed changes to `data/calendar/*.yaml`. In the production checkout,
run `git pull --ff-only`, then send `/sync` to the bot as administrator. Compose mounts
that directory into the running container, so calendar-only changes need no rebuild or
restart. The calendar updates immediately; use `/reviews` to approve a personalized
broadcast or save without sending. `/sync` does not run Git or research source websites.

For changes to application code, dependencies, migrations or Compose configuration, run
`docker compose up -d --build` after pulling. Startup applies migrations and imports the
calendar; broadcasts still require review.

## Memory budget

For a small private group on a 2 GiB server, Compose limits the bot to 384 MiB and
the backup service to 64 MiB. These are ceilings, not preallocated memory. Override
`BOT_MEMORY_LIMIT` and `BACKUP_MEMORY_LIMIT` in `.env` if the measured workload requires
more. Leave memory for the host, Docker and other services such as Xray/3x-ui.

The backup loop uses only Python's standard library, sleeps between runs and does not
load the Telegram framework. Sharing the application image does not mean sharing its
full disk size in RAM. The health probe checks SQLite read-only and worker heartbeats
without importing the bot or ORM. See [the memory audit](memory-audit-2026-09-08.md)
for measured consumption and practical limitations.

```sh
docker stats --no-stream olymping-bot-1 olymping-backup-1
```

Container limits apply at runtime; building the image has a separate peak. If the
production host cannot build comfortably alongside other services, build and transfer
the image from another machine before starting Compose with `--no-build`.

## Restore

For ordinary process restarts and upgrades, pending broadcasts stay pending and dismissed
batches stay dismissed. Approved unfinished broadcasts resume; scheduled reminders may
catch up within the configured grace period. The administrator can receive a pending-review
preview, but users do not receive an unapproved catalog broadcast. Keep the existing database
volume when upgrading: creating a fresh database discards delivery history.

Telegram flood-control deadlines persist in `olymping.telegram-cooldown.json` next to SQLite.
Keep that file when restarting or deploying. It contains only a deadline, no token. The
SQLite backup utility backs up the database itself, so the cooldown file must be copied
separately if moving hosts during an active Telegram pause. Only one polling process may
use the token; the in-process pacing is shared by all sends in that instance.

Delivery is paced at 10 messages/second by default (`TELEGRAM_MESSAGES_PER_SECOND`, 1–20).
A `429` defers background deliveries rather than exhausting their retry budgets or holding
a database transaction open throughout the cooldown. Lowering the rate stretches all
outgoing text messages, including reviewed broadcasts and daily digests.

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
