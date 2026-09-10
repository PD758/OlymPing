# Calendar refresh — 10 September 2026

Scope: `03_rsosh_selected.yaml`, `04_ctf_cup_russia.yaml`,
`07_rsosh_informatics_2026.yaml`, `11_law_olympiads.yaml`,
`12_economics_olympiads.yaml`, and `13_rosfin_olympiad.yaml`.

This is a primary-source recheck. No date was changed: the current files already
match the dates published by the organizers. Event and milestone IDs, progression
paths, and terminal markers were retained.

## Confirmed published calendars

- [«Высшая проба»](https://olymp.hse.ru/mmo/) confirms registration through
  21 September 2026 at 14:00 MSK, the second qualifying-tour period of
  13–22 November, and the final period of 5–15 February 2027. Its
  [first-tour table](https://olymp.hse.ru/mmo/timetable) remains expressly a
  project: Law is 25 September or 4 October; Economics is 26 or 30 September;
  Financial Literacy is 4 October; and Business Basics is 3 October. The
  [second-tour page](https://olymp.hse.ru/mmo/timetable1) says that Informatics
  has no first tour and that all registered participants take the second tour.
  Accordingly, the date-only alternatives remain `tentative`, the cancelled
  Informatics first-tour milestone remains in place, and inclusive windows retain
  their following-midnight `ends_at` values.
- The official [AI olympiad page](https://ai.edu.gov.ru/) gives registration and
  training through 20 September, the qualifier on 21 September–6 October, the
  main stage on 14–18 October, and the final on 16–21 November. The existing
  2026 dates and exclusive window boundaries encode those ranges. Its placement
  under `RSOSH` remains a preliminary categorization, not a new claim about an
  approved list.
- The official [CTF Cup Russia page](https://ctfcup.ru/) announces the 2026
  qualifying tour on 31 October–1 November. The stored `ends_at` of 2 November
  therefore remains correct. `OTHER` is intentional for this competition.
- The official [Rosfin stage page](https://rosfinolymp.ru/stages) distinguishes
  school dates from broader participant-group labels: school round 1 is 14 March
  and round 2 is 19 April, 10:00–14:00 MSK; motivation letters run 1 June–2
  September; school selection runs 2–3 September; and the final runs 27
  September–2 October. Existing entries preserve these school-specific dates,
  their progression, and exclusive ends on 3 September, 4 September, and
  3 October. The [participant page](https://rosfinolymp.ru/for-participants)
  confirms school eligibility for grades 8–10 at the qualifying round.

## Records with no newly published 2026/27 timetable

- The organizers linked by the existing records for Innopolis Open, Verchenko,
  Belyonok, ITMO Open, Lomonosov, Phystech, Step into the Future, IOIP, SPbU,
  Open Programming, Cognitive Technologies, Kutafin, Femida, Sibiriada, and the
  Lomonosov and SPbU economics profiles did not provide a newly verifiable
  timetable that supersedes the stored `tbd` or tentative record.
- The accessible UrFU [pre-university portal](https://dovuz.urfu.ru/) still
  points to completed `Изумруд` 2025/26 results rather than a replacement
  publication. The already stored 2026/27 dates were left unchanged.

The review does not infer a date, membership level, or stage from an earlier
season or a non-primary listing.
