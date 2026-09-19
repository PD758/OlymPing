# Calendar review — 19 September 2026 (Moscow)

Reviewed the 64 event IDs in `01_vosh_2026.yaml`, `05_mosh_2026.yaml`, and
`06_moscow_special_and_technocup.yaml` against their official public sources.
The review adds the newly published MOSH complex-security final theory and
practical-tour milestones. Every other stored date either matches the current
source or remains explicitly TBD where the source supplies no date.

## Sources and method

- VOSH school stage: the public `yearPage` response for `year=2026`,
  `psevdo=school`. It publishes a *project* schedule, specifies 09:00 on the
  first day through 21:00 on the last day, and distinguishes the 5–6 three-day
  access window from the 7–11 one-day competition. The two technology practical
  tours are independently listed as 15–21 September.
- VOSH municipal stage: the equivalent `psevdo=okrug` response. It says that
  preparation is under way and requests school data by 15 September; it does
  not publish a 2026/27 subject timetable. No 2025 dates were inferred.
- MOSH: public `api/schedule?year=2026&period=year`. It confirms the stored
  physics, art-history, probability-and-statistics, astronomy and complex-
  security entries. API `end` is the inclusive final calendar day, represented
  in YAML as the next midnight exclusive boundary.
- Technocup: current official landing page confirms 2026–27 registration,
  grades 8–11 and RSOSH level II, without a detailed schedule.

Raw captures (not versioned):

- `/tmp/calendar-20260919-vosh-school-api.json`
- `/tmp/calendar-20260919-vosh-okrug-api.json`
- `/tmp/calendar-20260919-mosh-schedule-2026-year-api.json`
- `/tmp/calendar-20260919-mosh-news-4596.html`
- `/tmp/calendar-20260919-mosh-news-4597.html`
- `/tmp/calendar-20260919-mosh-news-4668.html` (the page is a 2023 item; it
  was not used as current-cycle evidence)
- `/tmp/calendar-20260919-technocup.html`
- `/tmp/calendar-20260919-npk-science-for-life.html`
- `/tmp/calendar-20260919-npk-engineers.html`
- `/tmp/calendar-20260919-megapolis.html`

## Per-ID coverage

`confirmed` and `tentative` describe the current source basis; `unavailable`
means the official source currently offers no date, so the calendar retains
its existing TBD milestone.

| ID | Coverage / result |
| --- | --- |
| vosh:german-2026 | confirmed school registration 04 Sep and 7–11 single-day 11 Sep; municipal unavailable/TBD |
| vosh:literature-2026 | confirmed school registration 07 Sep and 7–11 single-day 14 Sep; municipal unavailable/TBD |
| vosh:technology-home-2026 | confirmed 15 Sep theory plus separate 15–21 Sep practical window; municipal unavailable/TBD |
| vosh:technology-technical-2026 | confirmed 15 Sep theory plus separate 15–21 Sep practical window; municipal unavailable/TBD |
| vosh:english-2026 | confirmed school registration 09 Sep and 7–11 single-day 16 Sep; municipal unavailable/TBD |
| vosh:social-science-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:obzr-2026 | official project schedule retained; practical 21–27 Sep remains separate; municipal unavailable/TBD |
| vosh:russian-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:astronomy-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:physical-culture-2026 | official project schedule retained; practical 24–30 Sep remains separate; municipal unavailable/TBD |
| vosh:history-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:italian-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:art-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:physics-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:spanish-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:informatics-robotics-2026 | official project schedule retained; practical window remains separate; municipal unavailable/TBD |
| vosh:geography-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:biology-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:french-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:ecology-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:mathematics-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:law-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:chemistry-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:chinese-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:informatics-programming-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:informatics-security-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:economics-2026 | official project schedule retained; municipal unavailable/TBD |
| vosh:informatics-ai-2026 | official project schedule retained; municipal unavailable/TBD |
| mosh:arabic-2026 | profile listed; date unavailable/TBD |
| mosh:astronomy-2026 | confirmed 04–17 Dec (YAML end 18 Dec 00:00) |
| mosh:biology-2026 | profile listed; date unavailable/TBD |
| mosh:bioeconomics-2026 | profile listed; date unavailable/TBD |
| mosh:probability-statistics-2026 | confirmed 18–24 Nov (YAML end 25 Nov 00:00) |
| mosh:genetics-2026 | profile listed; date unavailable/TBD |
| mosh:geography-2026 | profile listed; date unavailable/TBD |
| mosh:fine-art-2026 | profile listed; date unavailable/TBD |
| mosh:informatics-10-11-2026 | profile listed; date unavailable/TBD |
| mosh:informatics-6-9-2026 | profile listed; date unavailable/TBD |
| mosh:information-security-2026 | profile listed; date unavailable/TBD |
| mosh:history-2026 | profile listed; date unavailable/TBD |
| mosh:art-history-2026 | confirmed 14–22 Nov (YAML end 23 Nov 00:00) |
| mosh:complex-security-2026 | confirmed 12 Dec (YAML end 13 Dec 00:00), plus final theory 19 Mar 2027 and practical tour 20 Mar 2027 |
| mosh:linguistics-2026 | profile listed; date unavailable/TBD |
| mosh:math-festival-2026 | profile listed; date unavailable/TBD |
| mosh:moscow-mathematics-2026 | profile listed; date unavailable/TBD |
| mosh:social-science-2026 | profile listed; date unavailable/TBD |
| mosh:law-2026 | profile listed; date unavailable/TBD |
| mosh:preprofessional-engineering-2026 | profile listed; date unavailable/TBD |
| mosh:preprofessional-it-2026 | profile listed; date unavailable/TBD |
| mosh:preprofessional-research-2026 | profile listed; date unavailable/TBD |
| mosh:robotics-5-8-2026 | profile listed; date unavailable/TBD |
| mosh:robotics-9-11-2026 | profile listed; date unavailable/TBD |
| mosh:technology-home-2026 | profile listed; date unavailable/TBD |
| mosh:technology-technical-2026 | profile listed; date unavailable/TBD |
| mosh:physics-2026 | confirmed 15–22 Oct (YAML end 23 Oct 00:00) |
| mosh:philology-2026 | profile listed; date unavailable/TBD |
| mosh:financial-literacy-2026 | profile listed; date unavailable/TBD |
| mosh:chemistry-2026 | profile listed; date unavailable/TBD |
| mosh:ecology-2026 | profile listed; date unavailable/TBD |
| mosh:economics-2026 | profile listed; date unavailable/TBD |
| npk:science-for-life-2026 | current official page reviewed; 2026/27 dates unavailable/TBD |
| npk:engineers-of-the-future-2026 | current official page reviewed; 2026/27 dates unavailable/TBD |
| other:intellectual-megapolis-potential-2026 | current official page reviewed; 2026/27 dates unavailable/TBD |
| rsosh:technocup-2026 | registration confirmed; detailed schedule unavailable/TBD |
