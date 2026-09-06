# Release 0.2.0

The onboarding questionnaire selects class and subjects, then subscribes the user to
matching olympiads already in the calendar. `/onboarding` reopens it; existing registered,
ignored and subscribed choices are preserved. New administrators also complete the
questionnaire instead of being assigned grade 11 automatically.

Calendar imports apply immediately. All catalog, open-registration/participation and
daily-digest broadcasts now wait for administrator review. `/reviews` opens pending
batches: select individual olympiads, approve the selected items, or save without sending.
Each recipient receives only relevant items grouped into one message, with additional
parts only when Telegram limits require them. Ordinary scheduled reminders continue.

YAML patches are consolidated before computing the final difference against the database.
Date-change summaries show old and new values and shifts in days. Approval state,
per-event choices and delivery retries survive restarts. Repeated approval is idempotent;
changed review snapshots require refreshing before approval. Recipient access, interests
and open windows are checked again before delivery.

## Validation

- 66 automated tests passed, including real aiogram handler routing with mocked Telegram,
  recipient isolation, approval authorization, stale review handling and retry behavior.
- Ruff, mypy and Pyright passed.
- The frozen-lock Docker runtime image built successfully.
- A fresh online production backup was copied into an isolated, networkless container.
  Migration to `0005_notification_review` preserved all rows in the six checked user and
  delivery tables and passed SQLite foreign-key checks.
- Two imports on that copy each produced zero event/milestone changes and zero notices.

Run a single polling instance. Telegram delivery remains at-least-once around a crash
between sending a message and committing its delivery record. See [operations](operations.md)
for backup and restore procedures. The earlier production-readiness audit describes 0.1.0;
this release adds the onboarding and broadcast-review behavior above.
