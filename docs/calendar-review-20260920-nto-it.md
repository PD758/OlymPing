# Calendar review — NTO and IT Olympiads

Reviewed: 2026-09-20 (Moscow).

All 46 events in `02_nto.yaml`, `08_ai_olympiads.yaml`,
`09_programming_olympiads.yaml`, `10_nto_profiles.yaml`, and
`14_yandex_cup_2026.yaml` were rechecked against official organizer pages.
One stale final window was corrected to the tentative current-season period; all other assigned calendar data were retained.

## Fresh official-source findings

- [NTO schedule](https://ntcontest.ru/participants/schedule/) currently publishes the 2026/27 senior-track registration window (26 August–22 October), stage I (17 September–23 October), stage II (5 November–7 December with manual checking, or 11 December with automatic checking), and finals in February–April 2027. Stored inclusive windows use the following midnight as `ends_at`. Existing profile-backed final windows are retained; the flexible-electronics exception is described below.
- Each of the 34 recorded senior-profile URLs was opened directly. Their public schedule panels show shared dates, while explicitly stating that precise profile dates are in the Talant personal account. The flexible-electronics page required a direct uncached fetch: it still publishes 15 February–18 April **2026**, so it cannot support a 2027 exact final date. The current central NTO schedule only publishes “February–April 2027”; this is recorded as a tentative full-month window for that profile.
- The same NTO schedule and the [NTO Junior site](https://junior.ntcontest.ru/) publish Junior registration through 9 November, the online qualifier on 20 October–10 November, and regional finals on 7–17 December. The existing exclusive end dates (10 November registration, 11 November qualifier, 18 December final) remain correct.
- The [AI Challenge rules](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_4LKUUtO.pdf) remain the official dated source: qualifier through 15 September, main stage through 17 September 23:59 Moscow time, final 12–26 October, and defence 5–13 November. The existing `qualifier → team-stage → {final, defense}` graph is correct: the two terminal milestones are parallel outcomes of the main stage.
- The [RUDN DA/ML page](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) still identifies both competition stages as remote. Its currently exposed schedule view is a completed prior season; no newer official publication displaces the already recorded 2026/27 dates, so they are retained. The subject-specific remote-final statement continues to control the format.
- [DANO](https://dano.hse.ru/) continues to publish the recorded 2026 programme. [MKOShP](https://mkoshp.ru/) currently publishes 26 September, 4 October, 11 October, and 15 November for its four recorded rounds. All match the calendar.
- [Yandex Cup Analytics](https://yandex.ru/cup/analytics), [Algorithm](https://yandex.ru/cup/algorithm), and [ML](https://yandex.ru/cup/ml) publish the stored 2026 dates: Analytics/Algorithm practice 12–18 October and qualifier 1 November; ML qualifier 23 October–1 November; all three finals 27–29 November. Their registration deadline is “by 1 November”; date-only storage remains appropriate.
- [PROD](https://prodcontest.com/), [Keldysh](https://education.tbank.ru/school/olympiads/), [VKOShP](https://nerc.itmo.ru/school/russia-team/), and [VKOShP.Junior](https://education.tbank.ru/school/events/vkoshp-junior/) still provide no exact future-cycle dates. Their `tbd` milestones remain available and correct.

## Per-event disposition

### NTO — recorded dates retained

`nto:information-security-2026`, `nto:pift-2026`,
`nto:big-data-machine-learning-2026`, `nto:artificial-intelligence-2026`,
`nto:data-analysis-decision-making-2026`, and `nto-junior:iitech-2026`:
retained. Source availability: the official NTO senior/Junior schedule confirms
each shared applicable window; profile pages remain the event-level source URLs.

The following 29 senior profiles are also retained, with no generic-range
replacement of an existing exact profile date:

`nto:automation-business-processes-2026`,
`nto:intelligent-robotic-systems-2026`,
`nto:digital-sensor-systems-2026`, `nto:water-robotic-systems-2026`,
`nto:flexible-molecular-electronics-2026` (final corrected to the tentative central 2027 window),
`nto:chemical-industrial-technologies-2026`,
`nto:wireless-communications-2026`, `nto:genome-editing-2026`,
`nto:nanosystems-chemical-engineering-2026`,
`nto:rehabilitation-engineering-2026`,
`nto:engineering-biological-systems-2026`, `nto:urbanistics-2026`,
`nto:urban-engineering-networks-2026`, `nto:modeling-biotechnologies-2026`,
`nto:agroecological-control-2026`, `nto:infochemistry-2026`,
`nto:virtual-reality-technologies-2026`,
`nto:computer-game-development-2026`, `nto:mobile-app-development-2026`,
`nto:intelligent-energy-systems-2026`, `nto:nuclear-technologies-2026`,
`nto:quantum-engineering-2026`, `nto:chemical-power-sources-2026`,
`nto:space-imagery-geodata-2026`, `nto:satellite-systems-2026`,
`nto:aerospace-systems-2026`, `nto:autonomous-transport-systems-2026`,
`nto:unmanned-aircraft-systems-2026`, and `nto:flying-robotics-2026`.
Source availability: every official `ntcontest.ru` profile URL was available and
reviewed directly. Its public panel confirms the shared senior-track milestones;
only a publication with a precise profile date may justify changing a more
precise existing final date.

### Other IT/data events

- `other:ai-challenge-2026` — retained; official rules available and confirm all stored dates and the existing progression graph.
- `other:rudn-data-analysis-machine-learning-2026` — retained; official subject page available, confirms remote format; no superseding future-cycle schedule is available.
- `other:prod-2026` — retained as `tbd`; official page available, no exact current-cycle schedule.
- `other:dano-2026` — retained; official page available and continues to publish the stored programme.
- `other:keldysh-informatics-2026` — retained as `tbd`; official organiser page available, no next-season dates.
- `other:vkoshp-2026` — retained as `tbd`; official organiser page available, no 2026/27 dates.
- `other:vkoshp-junior-2026` — retained as `tbd`; official organiser page available, no next-season dates.
- `other:mkoshp-2026` — retained; official page available and confirms every recorded round date.
- `other:yandex-cup-analytics-2026`, `other:yandex-cup-algorithm-2026`, and `other:yandex-cup-machine-learning-2026` — retained; each official direction page is available and confirms its stored dates and Moscow in-person final.

## Change record

The final milestone of `nto:flexible-molecular-electronics-2026` changed from
the stale `2026-02-15`–`2026-04-18` inclusive public-profile window to the
central schedule’s tentative February–April 2027 period, stored as
`2027-02-01T00:00:00+03:00` through exclusive
`2027-05-01T00:00:00+03:00`. Its source is now the central NTO schedule and its
status is `tentative`; an exact 2027 final date has not been published. No IDs,
kinds, formats, or progression paths changed. All inclusive windows use
next-midnight-exclusive `ends_at`.
