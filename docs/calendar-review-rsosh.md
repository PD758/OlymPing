# RSOSH calendar review — 2026-09-06

Scope: every event in `data/calendar/03_rsosh_selected.yaml` and
`data/calendar/07_rsosh_informatics_2026.yaml`. Only organizer, university, government,
or RSOSH pages were used as evidence. The RSOSH page says the 2026/27 list is a *project*
(11 August 2026), so project-list membership is not treated as a final confirmation.

Official list status source: <https://rsr-olymp.ru/news/123>.

## `03_rsosh_selected.yaml` (5/5 reviewed)

| Event ID | Official source checked | Verified current-season facts | Calendar result / unknowns |
| --- | --- | --- | --- |
| `rsosh:innopolis-open-security-2026` | <https://dovuz.innopolis.university/pre-olympiads/innopolis-open/cyberbez> | 7–11 grades; two remote qualifying rounds and an in-person final are stated. The published dates are explicitly for 2025/26 and registration is closed. | Retained `tbd` 2026/27 schedule; no future date or membership inferred. |
| `rsosh:verchenko-2026` | <https://ikb.mtuci.ru/> | 8–11 grades; remote qualifying and in-person final are stated. Page dates are for 2025/26 only. | Retained `tbd`; 2026/27 dates and final RSOSH membership unavailable. |
| `rsosh:hse-informatics-2026` | <https://olymp.hse.ru/mmo/> | Registration ends 21 September 2026, 14:00 MSK; qualifier rounds are 25 September–11 October and 13–22 November; final period is 5–15 February 2027. Informatics is 9–11 grades. | The existing exclusive next-day-midnight window ends correctly encode the published inclusive end dates; no HSE date change was made. The organizer describes the profile as in the *project* list, so final-list membership remains unconfirmed. |
| `rsosh:belchonok-informatics-2026` | <https://dovuz.sfu.ru/> | Organizer page identifies the Belyonok olympiad but its material reaches only the completed 2025/26 season. | Retained `tbd`; 2026/27 timetable and membership unavailable. |
| `rsosh:itmo-open-informatics-2026` | <https://abit.itmo.ru/bachelor/olymp> | Organizer lists the Open Olympiad in Informatics. No 2026/27 schedule is published there. | Retained `tbd`; dates and membership unavailable. |

## `07_rsosh_informatics_2026.yaml` (10/10 reviewed)

| Event ID | Official source checked | Verified current-season facts | Calendar result / unknowns |
| --- | --- | --- | --- |
| `rsosh:all-russian-ai-2026` | <https://ai.edu.gov.ru/> | Registration/training: 1 July–20 September; qualifier: 21 September–6 October; main stage: 14–18 October (tour 1 is online 14–16 Oct, tour 2 is on-site 18 Oct); final: 16–21 November. Eligible school grades: 8–11. | Corrected deadline, main-stage and final windows; made mixed main stage `is_online: null`. Event status is `tentative` because RSOSH-list inclusion is only a project. |
| `rsosh:all-siberian-informatics-2026` | <https://sesc.nsu.ru/olymp/> | The configured organizer page could not provide a 2026/27 schedule in the review. The existing calendar records 6 Nov registration deadline, 8 Nov qualifier and 21 Feb final; a non-official search result was deliberately not used to newly verify or modify them. | Retained those existing dates as `tentative`, because the unavailable live page does not refute previously sourced data. Project-list membership remains unconfirmed. |
| `rsosh:izumrud-informatics-2026` | <https://dovuz.urfu.ru/> | Official organizer page states: 8–11 grades, included in the 2026/27 list, qualifier 1 September–19 January, final 30 January–2 February, online qualifier and in-person final. | Replaced source with the accessible official organizer page; corrected final start from 31 to 30 January and confirmed it. |
| `rsosh:lomonosov-informatics-2026` | <https://olymp.msu.ru/> | No 2026/27 informatcs timetable found on the organizer page. | Retained `tbd`; removed unsupported assertion that the schedule was expected in October. Project membership remains unconfirmed. |
| `rsosh:phystech-code-future-2026` | <https://olymp.mipt.ru/> | No 2026/27 Code Future timetable found. | Retained `tbd`; project membership remains unconfirmed. |
| `rsosh:step-future-informatics-2026` | <https://olymp.bmstu.ru/ru/programming-olymp> | 2025/26 material confirms an online qualifying stage, in-person final, and 8–11 grades, but no 2026/27 dates. | Retained `tbd`; project membership and future schedule remain unconfirmed. |
| `rsosh:ioip-2026` | <https://neerc.ifmo.ru/school/ioip/rules.html> | 2025/26 rules cover 11th grade only and a completed season; no 2026/27 schedule. | Retained `tbd`; replaced an unsupported February 2027 forecast with a neutral schedule milestone. |
| `rsosh:spbu-informatics-2026` | <https://olympiada.spbu.ru/> | No official 2026/27 informatics schedule found. | Retained `tbd`; removed unsupported October expectation. Project membership remains unconfirmed. |
| `rsosh:open-programming-2026` | <https://inf-open.ru/> | No official 2026/27 calendar found. | Retained `tbd`; removed unsupported November expectation. Project membership remains unconfirmed. |
| `rsosh:cognitive-technologies-2026` | <https://olymp.misis.ru/> | Organizer says 2025/26 is complete and information for the next year will appear in autumn 2026; 7–11 grades and level II are stated. | Retained `tbd`; removed unsupported November expectation. Project membership remains unconfirmed. |

Coverage: 15 of 15 events reviewed; 2 events had official 2026/27 date corrections or confirmations; 11 have no official 2026/27 timetable published on the reviewed organizer page, and 1 retains previously sourced dates as `tentative` pending live re-verification. All 15 retain their existing IDs.
