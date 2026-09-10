# Calendar review: Yandex Cup 2026

Reviewed 10 September 2026 (Europe/Moscow). All facts below come from the
organizer's current pages and the 2026 regulations.

## `data/calendar/14_yandex_cup_2026.yaml`

- Added three separate `OTHER` events for the current Yandex Cup directions:
  [Analytics](https://yandex.ru/cup/analytics),
  [Algorithm](https://yandex.ru/cup/algorithm), and
  [Machine Learning](https://yandex.ru/cup/ml). They have materially different
  qualification schedules, so they are not represented as a single event.
- The organizer's [regulations](https://yandex.ru/cup/regulations/) announce
  the 2026 competition on 10 September. They set the online qualification for
  Analytics and Algorithm on 1 November, ML from 23 October through 1 November,
  and the in-person Moscow final for 27–29 November. The direction pages
  independently show the same dates. Inclusive end dates are encoded as the
  next midnight: 18 October becomes `2026-10-19T00:00:00+03:00`, 1 November
  becomes `2026-11-02T00:00:00+03:00`, and 29 November becomes
  `2026-11-30T00:00:00+03:00`.
- Analytics and Algorithm additionally have an online practice round on
  12–18 October. It is explicitly a familiarization round and does not affect
  qualification, so it is recorded as an informational `other` milestone;
  qualification is the only recorded path to the final.
- Each direction page says registration is available through 1 November. The
  calendar records that day as a `registration_deadline` with `precision: date`;
  no registration-open date was invented. The regulations confirm registration
  through the online form before the competition.
- School access is confirmed through the junior stream: the junior regulations
  admit a participant from age 14 with written consent and supervision of a
  legal representative. No grade range is published, so `min_grade` and
  `max_grade` are intentionally omitted. Adults participate in the main stream
  from age 18. The regulations also state that a participant may qualify in ML
  and in one of Algorithm or Analytics, and may become a finalist in only one
  of those three directions; this is an entry/eligibility rule, not an
  inter-event advancement path.
