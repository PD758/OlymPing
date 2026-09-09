# OlymPing

OlymPing is an invitation-only Telegram calendar for school olympiads and CTF events. It imports a
reviewed YAML calendar, synchronizes upcoming events through the official CTFtime JSON API,
and sends persistent, customizable reminders.

The calendar contains all ВсОШ and МОШ profiles, all 34 senior НТО profiles, selected
РСОШ/NPK events, programming and AI competitions, and the Russian CTF Cup. The selected РСОШ catalog follows the preliminary 2026/27 list and marks
unconfirmed membership or dates as tentative or `tbd`; the bot never invents a date or sends
a reminder for an unconfirmed milestone.

## Features

- invitation-only multi-user access with separate settings, subscriptions, progress, and reminders;
- administrator-issued one-time links and reversible access blocking;
- today, 7-day, and 30-day views;
- a live "registration open now" section ordered by the nearest confirmed deadline;
- event interest (`Зарегистрирован` / `Не интересно`) and a separate result for every stage;
- stage outcomes: participated, passed, not passed, or skipped;
- independent notifications for newly indexed events, automatic subscription, and schedule changes;
- paginated catalog navigation with previous/next arrows that preserve the current filters;
- compact Telegram menus with colored actions, localized dates, and expandable details;
- school-grade and subject onboarding that subscribes to matching existing olympiads;
- school-grade, topic-tag, source, and CTFtime filters;
- multiple category defaults or per-event reminder overrides;
- idempotent YAML patches with source provenance;
- administrator review of grouped broadcasts, personalized delivery, and readable date changes;
- SQLite storage, Docker Compose deployment, tests, linting, and type checking.

## Quick start

Requirements: Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
# Fill TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID in .env
uv sync
uv run olymping doctor
uv run olymping bot
```

Create the bot token with BotFather. Obtain your numeric Telegram ID from a trusted Telegram
ID helper or the Bot API, and store it only in `.env`. That account becomes the administrator;
friends do not need to be added to `.env`.

Useful commands:

```bash
uv run olymping import-data
uv run olymping sync-ctftime
uv run olymping db-upgrade
uv run olymping doctor
uv run olymping healthcheck
uv run pytest
uv run ruff check .
uv run mypy
uv run pyright
```

## Telegram commands

At 09:00 Moscow time the bot prepares a daily registration digest for administrator review. It includes
confirmed registration openings in the preceding 24-hour window that match their filters,
excluding ignored, registered, cancelled, or already closed events. Empty digests are silent;
delivered events are recorded in SQLite to avoid repeats after a restart. Events without
a confirmed opening date are not included. This digest is independent of new-event notices.

- `/start` — onboarding for new users, otherwise the main menu;
- `/onboarding` — choose class and subjects again and select matching calendar events;
- `/today`, `/week` — calendar views;
- `/all` — all tracked olympiads, including schedules marked `tbd`;
- `/mine` — only subscribed or registered olympiads;
- `/register` — olympiads whose confirmed registration deadline has not passed;
- `/settings` — class, topic, source, and CTF filters;
- `/remind EVENT_ID DAYS HH:MM [KIND]` — add a per-event rule;
- `/remind EVENT_ID off` — mute an event;
- `/remind EVENT_ID default` — restore category defaults.

Administrator-only commands:

- `/invite` — create a one-time invitation link valid for seven days;
- `/users` — show users and block or unblock their access;
- `/revoke TELEGRAM_ID` — block a user while preserving their data;
- `/sync` — reload YAML, synchronize CTFtime, and prepare a review of changes and currently
  open registration or participation windows;
- `/reviews` — review pending broadcasts, select olympiads, approve delivery or save silently.

`Открытая регистрация и участие` in settings controls these notices and the administrator's
daily registration digest. Calendar data changes immediately, but every catalog, availability,
and digest broadcast requires administrator approval. The administrator receives one grouped
review (paginated for large updates), can exclude individual olympiads, then approve the rest
or save everything without a broadcast. Each recipient receives a personalized combined
message, split only when required by Telegram limits. Ordinary scheduled reminders continue
without review. Approved notifications are stored in SQLite and sent by the background
worker, normally within one minute. If reviewed data changes, approval requires refreshing
the review first; stale approved items are suppressed. Repeated `/sync` does not repeat delivered notices;
each participation stage and distinct registration opening is tracked separately. Ignored
events are excluded, and users already registered do not receive registration notices.
Only confirmed windows are announced. A participation stage needs a known end date;
unconfirmed dates are never inferred. The same check runs after startup and automatic sync.
If CTFtime is unavailable, the reviewed YAML calendar still updates.

A friend opens the invitation link and chooses their school grade and subjects, or explicitly
selects all subjects. Finishing the questionnaire subscribes them to matching existing
olympiads, visible in `/mine`. Existing registered or ignored choices are preserved. The
questionnaire can be reopened through `/onboarding` or settings. It adds matching subscriptions
without deleting previous choices; current filters control visibility and reminders. The invitation
cannot be reused. All later changes to class, filters, subscriptions, reminders, and stage results
belong only to that Telegram account. Blocking stops access and notifications without deleting
the profile, so `/users` can restore it later.

`Вся группа ВсОШ` and `Вся группа МОШ` include every subject from the chosen source that
passes the grade filter. Groups combine with individual subjects using OR: ВсОШ plus
programming includes all suitable ВсОШ events and programming events from other enabled
sources. Group selection works even when event subject tags are missing. Explicitly disabled
sources remain disabled. These choices are also available in the subject settings and apply
to future matching events, notifications and reminders.

New profiles start with the `CTF` source disabled. They can enable it in source settings;
existing profiles retain their previous choices. The separately curated Russian CTF Cup
uses `OTHER`, so it is not controlled by the CTFtime source switch.

Open an olympiad and choose `Этапы и результаты` to record whether you participated,
passed to the next stage, did not pass, or skipped a particular stage. `Не интересно`
mutes the whole olympiad while keeping it visible in `/all` so the choice can be reverted.

Personal views (`Сегодня`, `7 дней`, `30 дней`, and `Открыта регистрация`) exclude
events marked `Не интересно` by that user and events outside their current subject,
group, grade or source filters. Matching events need not already have a subscription
to appear. Limits apply after personal filtering; registrations are ordered by their
nearest deadline before truncating the list. Another user's choices have no effect.

Each event card contains one reminder toggle. `🔔 Напоминания: обычные` uses source defaults,
`⚙️ Напоминания: свои` means `/remind` overrides exist, and `🔕 Напоминания: выключены`
suppresses the event. Muting preserves custom rules so they can be restored with one tap.

The registration section requires a confirmed future `registration_deadline`. When a confirmed
`registration_open` milestone exists, the event appears only after it. With no separate opening
date, a future confirmed deadline is treated as an already available registration.

The settings keep two actions independent: `Сообщать о новых` controls catalog notices,
while `Автоподписка на новые` decides whether future events immediately receive normal
reminders. Changing either option does not rewrite existing subscriptions. The initial
catalog import is silent; only events discovered by later synchronizations are announced.

The grade filter treats the selected school grade as the minimum participation category. For
example, grade 9 shows olympiads with a grade 9, 10, or 11 category and hides events capped at
grade 8. Events whose age restrictions are still unknown remain visible. Topic tags use OR
semantics: an event remains visible when it matches at least one selected topic. The same
filters apply to the calendar, automatic subscriptions, change notices, and reminders.

For example, `/remind rsosh:hse-informatics-2026 1 20:00` adds an evening reminder one
calendar day before every milestone. Add `registration_deadline` as the final argument to
limit it to registration. Running the command several times creates several reminders.

## Calendar patches

Calendar files live in [`data/calendar`](data/calendar). Every event and milestone has a
stable lowercase ID, an official source URL, a status, and date precision. All timestamps
must include a UTC offset.

```yaml
calendar_version: 1
events:
  - id: rsosh:example-2026
    source_kind: RSOSH
    title: Example olympiad
    category: informatics
    tags: [rsosh, informatics, programming]
    source_url: https://example.edu/official
    status: confirmed
    restrictions: "7–11 grades"
    min_grade: 7
    max_grade: 11
    milestones:
      - id: rsosh:example-2026:registration-deadline
        kind: registration_deadline
        title: Registration deadline
        starts_at: "2026-10-10T18:00:00+03:00"
        precision: exact
        status: confirmed
        format: online testing system
        is_online: true
```

Import is transactional and idempotent. A later file may repeat the same IDs with updated
values. All files are validated and consolidated before computing changes against SQLite,
so intermediate values in older patches do not create repeated notifications. Date changes
show the old and new dates, including the shift in days where applicable. Omitting an event does not delete it; use `status: cancelled` explicitly. A changed
confirmed date supersedes unsent reminders and creates notices for matching active users.

Allowed source kinds are `VOSH`, `RSOSH`, `MOSH`, `NPK`, `NTO`, `CTF`, and `OTHER`. `NPK` is used
for school research and engineering conferences, including events from the Ministry of
Education's achievement registry. Milestone kinds are
`registration_open`, `registration_deadline`, `qualifier`, `team_stage`, `final`,
`competition`, and `other`.

## Docker deployment

The example `.env` uses local paths. Docker Compose overrides `DATABASE_URL` and `DATA_DIR`
with container paths, so the same configuration can be used for either launch method.

```bash
cp .env.example .env
# Set TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID
docker compose up -d --build
docker compose logs -f bot
```

Before the first Docker launch, prepare the backup directory with
`sudo ./scripts/setup-backups.sh`. The daily backup sidecar retains 14 verified copies in
`./backups`, outside the database volume. Copy these off-host to cover complete host loss.
See [operations and restore instructions](docs/operations.md).

The database is stored in the `olymping-data` volume. The calendar directory is mounted
read-only from the production checkout. For calendar-only changes, commit and push the
updated `data/calendar/*.yaml` files, then run on production:

```bash
git pull --ff-only
```

Send `/sync` to the bot as administrator. It imports the updated files immediately and
prepares any broadcasts for approval in `/reviews`. No image rebuild or restart is needed
for calendar-only changes, and the application version stays unchanged. `calendar_version`
is the YAML schema version and also stays unchanged when editing events or dates.
`/sync` does not fetch Git changes or research olympiad websites;
it reads the local YAML calendar and synchronizes the CTFtime API.

If application code, dependencies, migrations or deployment configuration changed, rebuild
and restart the services as well:

```bash
git pull --ff-only
docker compose up -d --build
```

To back up SQLite, stop the container briefly and copy `/app/data/olymping.db` from the
volume. Restore only while the bot is stopped. The accompanying `-wal` and `-shm` files are
not needed after a clean shutdown.

## Architecture

The `olymping` package separates SQLAlchemy models, validated external schemas, import and
sync services, reminder scheduling, Telegram handlers, and CLI wiring. SQLite values are
stored in UTC; wall-clock reminder rules use the profile's IANA timezone (`Europe/Moscow`
by default).

Event-level format is only a general description. Actual delivery mode, format, and location
belong to each milestone because different stages of one olympiad may be online and onsite.

Release 0.2.4 targets one polling instance with SQLite for a small invitation-only group.
Runtime health checks cover SQLite, successful Telegram polling, notification processing,
and CTFtime synchronization freshness. A watchdog restarts stalled core workers; a remote
CTFtime outage marks health degraded without discarding the local calendar.

Telegram sends and SQLite commits cannot form one transaction. An abrupt crash immediately
after a send can repeat that message; normal retries and restarts use persisted delivery
records. Registration digests cover the prior 24-hour window; `/sync` also discovers older
registrations that are still open, but does not announce already closed windows.

A restart or code deployment never approves pending broadcasts. Previously approved,
unfinished deliveries resume; already recorded deliveries do not repeat. Scheduled reminders
continue, including unsent occurrences within `REMINDER_GRACE_HOURS` (24 hours by default).
The administrator may receive a previously unannounced pending-review preview after restart.

Review deduplication compares facts across recipients and persists across restarts. Late
copies join the original pending review; facts already approved or dismissed are consumed
without a new review or retroactive broadcast to new recipients. Duplicate pending batches
are reconciled automatically on the next notification cycle. Different changes and new
participation phases still require review. Keep the persistent SQLite volume on deployment;
the review and delivery history lives there.

For subscribed olympiads, default reminders include 20:00 on the day before registration
closes, in the user's timezone. No administrator review is needed for this personal reminder.
The “registered” mark suppresses registration reminders; ignored events, disabled sources
and muted event reminders are also respected. Custom event rules override the defaults.
Date-only deadlines are displayed as inclusive dates, and expired registration reminders
are not sent during catch-up after downtime.

All `sendMessage` calls share pacing: 10 messages/second by default, at least 1.1 seconds
between messages in a private chat and 3.1 seconds in a group. Configure
`TELEGRAM_MESSAGES_PER_SECOND` between 1 and 20. Daily digests, approved `/sync` broadcasts,
reminders and administrator previews use this same budget. Telegram `retry_after` pauses
are saved beside the database as `*.telegram-cooldown.json` and survive process restarts.
Background delivery is deferred without consuming retry attempts; polling stays active.
The bot does not enable paid broadcasts. These conservative limits follow the
[Telegram FAQ](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this)
and still honor the [API's dynamic flood-control response](https://core.telegram.org/bots/api#responseparameters).

CTFtime is queried at a low frequency and cached locally. OlymPing is a personal notification
tool, not a CTFtime clone; descriptions are truncated and every event links to its source.

## License

[MIT](LICENSE)
