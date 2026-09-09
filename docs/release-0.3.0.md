# Release 0.3.0

## Behavior

Stage outcomes control eligibility through explicitly curated paths. Unknown results retain
calendar entries and reminders; unsuccessful prerequisites block only dependent paths.
Terminal stages do not produce requests to confirm advancement. Personal requests and
administrator schedule-gap alerts use a persistent delivery ledger and shared Telegram pacing.
The `/gaps` command shows currently unresolved gaps even if delivery failed.

Imports reapply saved questionnaires to automatic subscriptions. All pre-upgrade preferences
are migrated as manual: this release deliberately does not guess which old subscriptions
came from an earlier questionnaire. Manual subscriptions bypass only topic/group matching,
not source switches or the existing maximum-grade rule. Explicit unsubscribe is retained as
`unsubscribed` rather than deleted, preventing automatic resubscription on the next import.

Personal subscription changes require the existing broadcast approval. They are not deduplicated
as global event changes across users, and removal notices remain deliverable after topic mismatch.
Card and questionnaire buttons accompany the notification. Sending remains subject to user
notification settings and active access.

## Calendar format

Schema version remains 1 with optional milestone fields:

```yaml
- id: example:qualifier
  kind: qualifier
  title: Отбор
  advancement_paths: []       # explicitly open entry stage
  terminal: false
  # results_at: "2026-10-20T20:00:00+03:00"  # only when officially known
- id: example:final
  kind: final
  title: Финал
  advancement_paths:
    - [example:qualifier]      # all entries in one path must be passed
    # - [example:alternative]  # another path would be an alternative
  terminal: true
```

Omission/null means the progression has not been curated, not rejection of the participant.
References must be within the same event; cycles, missing references and successors of a
terminal stage are rejected before import. Connections use named stages and known formats,
never sorting by dates to infer qualification. VOSH levels and NTO tracks have explicit
connections; DANO's two final tours both depend on the second qualifier, not each other.
The [DANO organizer](https://dano.hse.ru/) documents both qualifying rounds and the final tours;
the [NTO schedule](https://ntcontest.ru/participants/schedule/) describes its three-stage structure.
Other uncurated schedules stay open and produce an administrator gap when a confirmed stage ends.
No result-publication dates were invented.

Label corrections include informatics for MOSH preprofessional IT; mathematics for probability
and statistics; biology for genetics; art for fine art and art history; team for PROD; research
and preprofessional for Engineers of the Future. Source classification, disputed AI labels
and age policy remain unchanged.

## Upgrade

1. Keep a current SQLite backup and the persistent data volume.
2. After pushing the release, run `git pull --ff-only` and `docker compose up -d --build` on prod.
3. Startup applies migration `0006_progression_subscriptions` and imports the calendar. Review
   subscription changes in `/reviews`; `/sync` may be used again safely.
4. Pending reviews from the older version may require “Обновить сведения” because their
   snapshots did not include progression metadata. Approval remains manual.

For rollback, restore a matching backup and the preceding application/calendar revision together;
older parsers do not understand the new optional YAML fields or `awaiting_results` outcome.
Normal restarts use persisted delivery records. Telegram sending and SQLite commits still cannot
be one transaction: a crash between a successful send and its commit can repeat that message.
