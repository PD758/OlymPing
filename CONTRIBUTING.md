# Contributing

Thank you for improving OlymPing.

## Code changes

1. Install Python 3.13+ and `uv`.
2. Run `uv sync`.
3. Keep domain logic outside Telegram handlers where practical.
4. Add tests for behavioral changes.
5. Run `uv run ruff format .`, `uv run ruff check .`, `uv run mypy`, and `uv run pytest`.

Never commit a bot token, Telegram ID, production database, or copied private data.

## Calendar changes

- Prefer the organizer's official page over aggregators and social reposts.
- Include `source_url` for the event and changed milestone.
- Use `confirmed` only when the source contains an actual date.
- Use an explicit UTC offset and preserve the organizer's stated timezone.
- Keep existing IDs when a date changes.
- Mark cancellations explicitly; never remove an event to represent cancellation.
- Avoid copying long event descriptions. Facts, short summaries, and source links are enough.

Validate a patch with `uv run olymping doctor` and include the official source in the pull
request description.
