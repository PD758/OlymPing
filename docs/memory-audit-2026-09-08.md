# Memory audit — 8 September 2026

Target: a small private group on a 2 GiB server sharing the host with Xray/3x-ui.
Measurements below were made locally on Linux with the Python 3.13 Docker image;
they are observations, not a guarantee for another workload or host.

## Before

- `docker stats --no-stream`: bot about 201 MiB, backup service about 11 MiB.
- Bot PID 1 RSS: about 216 MiB, four threads.
- The health probe launched `olymping healthcheck` every 60 seconds. Importing the
  CLI imported the entire bot, aiogram, SQLAlchemy and calendar machinery. A fresh
  container's import chain peaked at 198 MiB. A live cgroup sample during the probe
  and a small measurement process reached about 388 MiB.
- The backup service already uses only the standard library and SQLite's online
  backup API. It sleeps between daily backups and is not the main memory expense.

## Changes

- CLI imports the bot only for the `bot` command and database/import services only
  for commands that need them.
- The health probe opens SQLite read-only with the standard library and checks
  the same runtime worker heartbeats. It does not run migrations or create a
  missing database. The watchdog checks are retained.
- A complete SQLite + heartbeat probe with the new code peaked at **37.7 MiB**
  in an isolated container, about **160 MiB less** than the old import chain.
- Compose limits bot memory to 384 MiB and backup memory to 64 MiB, configurable
  through `.env`. These caps are not reservations of that amount of physical RAM.
  The backup service and its daily verified backups remain enabled.

The main bot still has the aiogram baseline; this change targets health-probe peaks,
not a promised 130 MiB steady-state footprint. Do not infer a memory leak from a
single RSS sample: compare idle, sync, notification and health-probe periods.
Image building has a separate memory budget from running the services.

## After deployment

With 121 YAML events (including 34 senior НТО profiles) and the existing CTFtime
catalog, `docker stats` reported **199.4 MiB / 384 MiB** for the bot and
**10.57 MiB / 64 MiB** for backups. Both services were healthy. The initial bot
cgroup peak was 225.9 MiB; `memory.events` reported zero OOM kills and zero limit
hits. The full new healthcheck also passed when invoked manually. These are short
post-deployment samples, not a long-running load-test guarantee.

## Validation

Tests cover missing-database rejection without creation, avoiding Telegram/ORM imports
in the CLI, database health, and fresh/stale worker heartbeats. Resource limits are
validated by Docker Compose and checked after deployment. The production host's
other services were not measured; leave headroom for them and the OS.
