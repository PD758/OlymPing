# Release 0.2.2

New profiles have the CTFtime source disabled by default. Existing profiles retain
both explicit settings and the historical enabled meaning of missing source keys.
The separately curated Russian CTF Cup remains an OTHER-source event.

All outgoing `sendMessage` calls now share one pacing middleware: 10 messages per
second, at least 1.1 seconds between sends to a private chat, and 3.1 seconds for a
group. `TELEGRAM_MESSAGES_PER_SECOND` accepts 1–20. This covers daily digests,
approved review batches, reminders, administrator previews and interactive replies.
Polling and callback acknowledgements are not delayed by message pacing.

Telegram `429` responses persist the supplied cooldown beside SQLite and apply it
to all sends, including after a process restart. Background jobs keep their pending
delivery records and retry budgets, release their database transaction and resume
in a later cycle. Interactive replies wait asynchronously. No paid broadcasts are
requested. Successful reminders are committed individually before the next send.

## Restart and deployment audit

- Startup imports data and queues availability notices; it does not approve broadcasts.
- Pending and dismissed batches do not send on restart. Approved unfinished batches
  continue, and recorded successful deliveries are not repeated.
- New or changed calendar entries on deployment still require administrator review.
- The administrator may receive the preview of a pending review after restart.
- Ordinary scheduled reminders continue, including eligible unsent occurrences in the
  configured 24-hour grace window. This is intentional existing behavior.
- Telegram and SQLite cannot share a transaction. A crash after Telegram accepted a
  message but before its delivery commit can still duplicate that one message.

## Validation

82 tests passed, including actual database preparation across restarts, pending/dismissed/
approved reviews, changes introduced on deployment, partial reminder interruption,
100-recipient pacing, concurrent senders, persisted flood waits, and CTF defaults.
Ruff, mypy and Pyright checks passed. No local polling instance was started, because
the user has moved the bot to production. Upgrade production with the existing
database volume; no new schema migration is required.

Sources checked on 8 September 2026:
[Telegram broadcast limits](https://core.telegram.org/bots/faq#my-bot-is-hitting-limits-how-do-i-avoid-this),
[retry_after](https://core.telegram.org/bots/api#responseparameters).
