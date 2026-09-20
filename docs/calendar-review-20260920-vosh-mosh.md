# Calendar review — 20 September 2026 (Moscow)

Reviewed all 64 event IDs in `01_vosh_2026.yaml`, `05_mosh_2026.yaml`, and
`06_moscow_special_and_technocup.yaml` against the official public pages as
available on 20 September 2026, Moscow time.  No date, ID, kind, or existing
exclusive end boundary changed: the fresh sources agree with the calendar.

## Sources and interpretation

- **VOSH school stage:** [`/api/yearPage`](https://vos.olimpiada.ru/api/yearPage),
  posted with `year=2026`, `psevdo=school`, marks the timetable as a *project
  schedule*.  It retains the stored school-stage dates.  Where a news item
  gives two access periods, the calendar's existing milestone deliberately
  represents the 7–11 competition day (09:00–21:00); the broader 5–6 access
  period does not replace that date.
- **VOSH news review:** the current individual official news items checked were
  4 Sep, “Открыта регистрация на школьный этап по немецкому языку”; 7 Sep,
  “Открыта регистрация на школьный этап по литературе”; 8 Sep, “Открыта
  регистрация на школьный этап по культуре дома, дизайну и технологии”; 9 Sep,
  “Открыта регистрация на школьный этап по английскому языку”; and 15 Sep,
  “Стартовал школьный этап по технике, технологии и техническому творчеству”.
  They confirm the corresponding registrations, 7–11 competition dates, and
  both technology practical windows (15–21 Sep).
- **VOSH municipal stage:** the fresh `year=2026`, `psevdo=okrug` response says
  preparation is under way and that EКИС data collection ran through 15 Sep.
  Its displayed subject timetable is explicitly for 2025/26.  It publishes no
  2026/27 municipal subject dates.  This is recorded as unavailable/TBD, not
  as evidence against any retained event.
- **MOSH:** the required full-year feed
  [`api/schedule?year=2026&period=year`](https://mos.olimpiada.ru/api/schedule?year=2026&period=year)
  was used (not a monthly view).  It contains seven dated records.  Its `end`
  is an inclusive final calendar day; YAML correctly uses midnight immediately
  after that day as the exclusive `ends_at` value.
- **Special events:** their current official landing pages were checked.  The
  two NPK pages and MИСИС page show material for the completed 2025/26 cycle,
  without 2026/27 milestone dates.  Technocup confirms registration for
  2026–27, grades 8–11 and RSOSH level II; its displayed detailed timetable is
  headed “25/26”, so it is not applied to the 2026 event.

## Per-ID result

`confirmed` means the current source supports the stored dated milestone(s).
`project` is a current official VOSH project timetable. `unavailable` means the
official source supplies no new-cycle date and the existing TBD milestone is
retained.

| ID | Result and current source |
| --- | --- |
| vosh:german-2026 | confirmed — 4 Sep VOSH news: registration 4 Sep; 7–11 on 11 Sep. Municipal unavailable. |
| vosh:literature-2026 | confirmed — 7 Sep VOSH news: registration 7 Sep; 7–11 on 14 Sep. Municipal unavailable. |
| vosh:technology-home-2026 | confirmed — 8 Sep VOSH news: theory 15 Sep; practical 15–21 Sep. Municipal unavailable. |
| vosh:technology-technical-2026 | confirmed — 15 Sep VOSH news: theory 15 Sep; practical 15–21 Sep. Municipal unavailable. |
| vosh:english-2026 | confirmed — 9 Sep VOSH news: registration 9 Sep; 7–11 on 16 Sep. Municipal unavailable. |
| vosh:social-science-2026 | project — VOSH school API; municipal unavailable. |
| vosh:obzr-2026 | project — VOSH school API, including the separate practical window; municipal unavailable. |
| vosh:russian-2026 | project — VOSH school API; municipal unavailable. |
| vosh:astronomy-2026 | project — VOSH school API; municipal unavailable. |
| vosh:physical-culture-2026 | project — VOSH school API, including the separate practical window; municipal unavailable. |
| vosh:history-2026 | project — VOSH school API; municipal unavailable. |
| vosh:italian-2026 | project — VOSH school API; municipal unavailable. |
| vosh:art-2026 | project — VOSH school API; municipal unavailable. |
| vosh:physics-2026 | project — VOSH school API; municipal unavailable. |
| vosh:spanish-2026 | project — VOSH school API; municipal unavailable. |
| vosh:informatics-robotics-2026 | project — VOSH school API, including the separate practical window; municipal unavailable. |
| vosh:geography-2026 | project — VOSH school API; municipal unavailable. |
| vosh:biology-2026 | project — VOSH school API; municipal unavailable. |
| vosh:french-2026 | project — VOSH school API; municipal unavailable. |
| vosh:ecology-2026 | project — VOSH school API; municipal unavailable. |
| vosh:mathematics-2026 | project — VOSH school API; municipal unavailable. |
| vosh:law-2026 | project — VOSH school API; municipal unavailable. |
| vosh:chemistry-2026 | project — VOSH school API; municipal unavailable. |
| vosh:chinese-2026 | project — VOSH school API; municipal unavailable. |
| vosh:informatics-programming-2026 | project — VOSH school API; municipal unavailable. |
| vosh:informatics-security-2026 | project — VOSH school API; municipal unavailable. |
| vosh:economics-2026 | project — VOSH school API; municipal unavailable. |
| vosh:informatics-ai-2026 | project — VOSH school API; municipal unavailable. |
| mosh:arabic-2026 | unavailable — profile present in full-year MOSH feed; no dated event. |
| mosh:astronomy-2026 | confirmed — 4–17 Dec; YAML exclusive end 18 Dec 00:00. |
| mosh:biology-2026 | unavailable — profile present; no dated event. |
| mosh:bioeconomics-2026 | unavailable — profile present; no dated event. |
| mosh:probability-statistics-2026 | confirmed — 18–24 Nov; YAML exclusive end 25 Nov 00:00. |
| mosh:genetics-2026 | unavailable — profile present; no dated event. |
| mosh:geography-2026 | unavailable — profile present; no dated event. |
| mosh:fine-art-2026 | unavailable — profile present; no dated event. |
| mosh:informatics-10-11-2026 | unavailable — profile present; no dated event. |
| mosh:informatics-6-9-2026 | unavailable — profile present; no dated event. |
| mosh:information-security-2026 | unavailable — profile present; no dated event. |
| mosh:history-2026 | unavailable — profile present; no dated event. |
| mosh:art-history-2026 | confirmed — 14–22 Nov; YAML exclusive end 23 Nov 00:00. |
| mosh:complex-security-2026 | confirmed — 12 Dec qualifier (exclusive end 13 Dec 00:00), final theory 19 Mar 2027, practical 20 Mar 2027. |
| mosh:linguistics-2026 | unavailable — profile present; no dated event. |
| mosh:math-festival-2026 | unavailable — profile present; no dated event. |
| mosh:moscow-mathematics-2026 | unavailable — profile present; no dated event. |
| mosh:social-science-2026 | unavailable — profile present; no dated event. |
| mosh:law-2026 | unavailable — profile present; no dated event. |
| mosh:preprofessional-engineering-2026 | unavailable — profile present; no dated event. |
| mosh:preprofessional-it-2026 | unavailable — profile present; no dated event. |
| mosh:preprofessional-research-2026 | unavailable — profile present; no dated event. |
| mosh:robotics-5-8-2026 | unavailable — profile present; no dated event. |
| mosh:robotics-9-11-2026 | unavailable — profile present; no dated event. |
| mosh:technology-home-2026 | unavailable — profile present; no dated event. |
| mosh:technology-technical-2026 | unavailable — profile present; no dated event. |
| mosh:physics-2026 | confirmed — 15–22 Oct; YAML exclusive end 23 Oct 00:00. |
| mosh:philology-2026 | unavailable — profile present; no dated event. |
| mosh:financial-literacy-2026 | unavailable — profile present; no dated event. |
| mosh:chemistry-2026 | unavailable — profile present; no dated event. |
| mosh:ecology-2026 | unavailable — profile present; no dated event. |
| mosh:economics-2026 | unavailable — profile present; no dated event. |
| npk:science-for-life-2026 | unavailable — official NPK page has completed 2025/26 material only. |
| npk:engineers-of-the-future-2026 | unavailable — official NPK page has completed 2025/26 material only. |
| other:intellectual-megapolis-potential-2026 | unavailable — official MИСИС page shows 17–18 Jan 2026, a completed-cycle date, not 2026/27. |
| rsosh:technocup-2026 | confirmed registration; 2026/27 detailed milestones unavailable because the page's schedule is labelled 25/26. |

Raw non-versioned captures used for the review are under `/tmp/calendar-20260920-*`.
