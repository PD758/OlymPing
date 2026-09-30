# Calendar and gaps review — 30 September 2026

Scope: all 14 calendar files (138 existing events), current schedule gaps, and the
user-supplied `Календарь олимпиад по информатике.xlsx`. Three gpt-5.6-terra agents
reviewed VOSH/MOSH, NTO/Yandex, and programming/AI. Root reviewed law/economics,
Rosfin/CTF, integrated the changes, and checked progression behavior.

## Changes

- **MOSH financial literacy:** added invitation registration from 22 September
  and tasks **26 September 09:00–3 October 21:00 MSK**, for grades 5–11 in Moscow
  schools. The [22 September announcement](https://mos.olimpiada.ru/news/4604)
  and [28 September follow-up](https://mos.olimpiada.ru/news/4607) agree. Their
  full bodies were read via `/api/news/4604` and `/api/news/4607`, because the
  frontend renders only a loading placeholder. The full-year schedule API gives
  a conflicting 3 November end; the dated, explicit announcements take priority.
  A separate registration cutoff is not inferred from the task deadline.
  This invitation is an independent terminal stage: the organizer explicitly says
  its scores do not affect participation in later rounds. It must not ask the user
  to confirm qualification to the next round.
- **All-Russian AI:** connected qualifier → main → final according to the
  [organizer's stage descriptions](https://ai.edu.gov.ru/). Existing dates and IDs
  are preserved; the links prevent two future missing-continuation gaps.
- **DANO:** [first-round instructions](https://dano.hse.ru/first) specify
  9 October 08:00–12 October 23:59 Moscow time. Replaced the day-only window with
  exact timestamps and linked the specific source.
- **Higher Test law, economics, financial literacy, business basics:** connected
  the first round to the second using [regulation §2.2.1](https://olymp.hse.ru/mirror/pubs/share/1177293678.pdf).
  For law/economics, either first-round date is sufficient (OR, not AND). Added
  class-specific first-round start times to descriptions from the
  [approved timetable](https://olymp.hse.ru/mmo/timetable). Dates remain day-level
  milestones because the schema does not assign individual stages to grades.
  Final access remains uncurated: §2.9 also admits previous-year winners and
  winners of other designated contests, which the existing model cannot express
  as a complete set of alternative routes.

## Current gaps

Using `missing_schedule` on the file-backed calendar at 30 September 12:00 MSK:
**18 before, 16 after**. The two resolved current gaps are the first Higher Test
rounds in law and economics. A regression test also checks financial literacy and
business basics before their first rounds finish, accepts either alternative date,
resolves already queued gap notices, and does not repeat notices after re-import.

All remaining current gaps belong to VOSH school stages. The
[municipal page](https://vos.olimpiada.ru/2026/okrug), including its POST
`/api/yearPage` response (`year=2026`, `psevdo=okrug`, `textField=ds2`), still shows
preparation for the season and the **2025/26** timetable. Those dates were not
copied into 2026/27.

| Subject | Completed stages waiting for a confirmed municipal schedule |
| --- | --- |
| German | School stage |
| Literature | School stage |
| Labour: home culture, design and technology | Theory and practical rounds |
| Labour: engineering and technical creativity | Theory and practical rounds |
| English | School stage |
| Social science | School stage |
| OBZR | Theory and practical rounds |
| Russian | School stage |
| Astronomy | School stage |
| Physical culture | Theory round |
| History | School stage |
| Italian | School stage |
| Art | School stage |

These counts do not include production users' manual stage-completion flags;
the production DB was not available or modified. A separate conservative scan
also examined gaps that could appear after a user reports completion early.
No `terminal` flag was added to suppress an unknown continuation.

## Schedule coverage and unresolved items

| File/group | Events | Result |
| --- | ---: | --- |
| VOSH | 28 | School dates retained; municipal dates still unavailable. |
| NTO, including Junior | 35 | All 34 senior profile pages and shared applicable schedules checked. No date changes. Flexible-electronics final retains the tentative February–April 2027 window; its profile still has a stale 2026 year. Student-track dates were not applied. |
| Selected RSOSh + informatics | 16 | All-Russian AI links corrected; remaining confirmed dates retained and unpublished dates left TBD. |
| CTF Cup Russia | 1 | Official rules confirm registration deadline 25 October 12:00, qualifier 31 October–1 November, school final 4 December. |
| MOSH | 32 | Full-year schedule checked; financial-literacy invitation added. |
| Moscow conferences + Technocup | 4 | No confirmed next-cycle NPK timetable. Technocup advertises 2026/27 but detailed dates still belong to 2025/26. |
| Other AI | 2 | AI Challenge dates and existing progression verified. RUDN's official page timed out on two fresh attempts (20/60 seconds); its prior data was preserved, not treated as newly confirmed. |
| Programming contests | 6 | DANO hours refined; MKOShP/VKOShP dates retained. PROD, Junior and Keldysh exact next-cycle dates unavailable. |
| Law | 4 | Higher Test progression/time descriptions corrected. Kutafin/Femida dates retained; Lomonosov still has only a broad seasonal announcement. |
| Economics | 6 | Three Higher Test profiles corrected. SPbU dates retained; Sibiriada still gives only upper bounds, Lomonosov only a broad period. |
| Rosfin | 1 | Current school final 27 September–2 October and existing selection links confirmed. |
| Yandex Cup | 3 | Algorithm, ML and Analytics pages agree with the calendar. |

The Izumrud registration deadline remains unresolved: the UrFU homepage says
18 January while the competition page combines registration/qualification through
19 January. No exact registration deadline was invented.

Root sources were freshly downloaded to `/tmp/olymping-root-sources-0930/index.json`.
Other temporary evidence/outcomes are in the three agent reports under
`/tmp/olymping-*-0930-report.txt`. Temporary captures are not versioned.

## Spreadsheet comparison

Read all nine sheets without changing the workbook. The useful current-season
sheet is `2026-2027`; older sheets and the hidden regional-selection sheet were
identified as historical. Dates are interpreted with Excel's 1899-12-30 epoch.

- `A13` = 11 October 2026 and `A26` = 15 November 2026 agree with MKOShP's
  professional qualifier/final. DANO and the initial All-Russian AI dates agree.
- `A51` = 19 December 2026 agrees with the MOSH 6–9 qualifier.
- `A66`, `A84`, `A85`, `A95`, `A97`, `A112` contain January–March **2026**, despite
  the sheet's 2026–2027 title. They were not shifted to 2027 or imported.
- Hidden sheet `Региональные отборы на ВКОШП ` contains **2019** dates.
- New pointers [Junior/Letovo](https://vkoshp.letovo.ru/) and
  [Keldysh/Sirius](https://www.keldysh.siriusolymp.ru/) still describe the completed
  2026 season, so they do not resolve next-season gaps.
- Coverage candidates: FAIO, Innopolis Open AI, Rosatom informatics, Gazprom
  informatics, Vuzovsko-akademicheskaya informatics and BSUIR Open. These are
  separate competitions/profiles; none was added during this update.

## Verification

Updated 7 existing events. The calendar contains 138 events and 494 milestones.
All 27 selected schema/import, progression and calendar tests pass, including
four new HSE transition cases. Ruff and `git diff --check` pass.

Imported the baseline into an isolated SQLite database, then applied this update:
5 event-level updates, 1 new milestone, 14 milestone updates, 0 notices in the
userless database. A second import produced 0 changes and 0 notices. Separate
progression tests use simulated users and verify resolution of existing gap notices.

Application version and existing event/milestone IDs are preserved. No push,
production import, bot startup, or Telegram send was performed.
