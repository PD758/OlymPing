# Calendar review — NTO and IT Olympiads

Reviewed: 2026-09-15 (Moscow).

This review covers every event in the five assigned calendar files. The source checks used current official organizer pages, fetched on the review date. Date-only inclusive end dates are represented by the next midnight where a window is stored.

## Sources and changes

- [NTO schedule](https://ntcontest.ru/participants/schedule/) publishes the 2026/27 senior-track registration period (26 August–22 October 2026), Stage I (17 September–23 October), Stage II (5 November–7/11 December), and finals in February–April 2027. The final range is shared and month-level, so it is not stronger evidence than the existing precise profile final windows. The six NTO events in `02_nto.yaml` and 29 in `10_nto_profiles.yaml` therefore retain their dates, IDs, paths, and terminal fields.
- [AI Challenge](https://aiijc.com/) continues to publish the 2026 cycle, including registration through 15 September inclusive; its existing milestones remain supported.
- [RUDN DA/ML profile](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) publishes the 2026/27 dates already recorded: registration 15 September 2026–25 January 2027, online qualifier 1 October 2026–25 January 2027, and final 13–18 February 2027.
- [DANO](https://dano.hse.ru/) confirms its recorded 2026 schedule: registration 31 August–5 October, first qualifier 9–12 October, second qualifier 1 November, task tour 18 December, and project tour 18–23 December.
- [MKOShP](https://mkoshp.ru/) has now published a current 2026 schedule. The event changed from TBD to confirmed: amateur qualifier 26 September; amateur final 4 October; professional qualifier 11 October; professional final 15 November. The existing `:schedule` ID was retained for the first stage. The professional qualifier has no calendar progression link because the official eligibility also admits teams through the prior regional Olympiad; the professional final retains paths from its published qualifier and directly invited amateur-final teams.
- [Yandex Cup](https://yandex.ru/cup/algorithm) current direction pages confirm the recorded schedule: ML qualification 23 October–1 November, Algorithm/Analytics qualification 1 November, and the in-person final 27–29 November. The stored next-midnight window ends are correct.

## Event outcomes

| Event ID | Outcome | Official source |
|---|---|---|
| `nto:information-security-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:pift-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:big-data-machine-learning-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:artificial-intelligence-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:data-analysis-decision-making-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto-junior:iitech-2026` | retained — no changed current-season evidence | [NTO Junior](https://junior.ntcontest.ru/) |
| `nto:automation-business-processes-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:intelligent-robotic-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:digital-sensor-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:water-robotic-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:flexible-molecular-electronics-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:chemical-industrial-technologies-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:wireless-communications-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:genome-editing-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:nanosystems-chemical-engineering-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:rehabilitation-engineering-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:engineering-biological-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:urbanistics-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:urban-engineering-networks-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:modeling-biotechnologies-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:agroecological-control-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:infochemistry-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:virtual-reality-technologies-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:computer-game-development-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:mobile-app-development-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:intelligent-energy-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:nuclear-technologies-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:quantum-engineering-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:chemical-power-sources-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:space-imagery-geodata-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:satellite-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:aerospace-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:autonomous-transport-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:unmanned-aircraft-systems-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `nto:flying-robotics-2026` | retained — no stronger profile-specific final evidence | [NTO schedule](https://ntcontest.ru/participants/schedule/) |
| `other:ai-challenge-2026` | retained — 2026 cycle remains published | [AI Challenge](https://aiijc.com/) |
| `other:rudn-data-analysis-machine-learning-2026` | retained — 2026/27 schedule remains published | [RUDN](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) |
| `other:prod-2026` | retained as TBD — official page describes stages but provides no current exact cycle dates | [PROD](https://prodcontest.com/) |
| `other:dano-2026` | retained — 2026 dates confirmed | [DANO](https://dano.hse.ru/) |
| `other:keldysh-informatics-2026` | retained as TBD — current official page has no exact Olympiad cycle dates | [T-Образование](https://education.tbank.ru/school/olympiads/) |
| `other:vkoshp-2026` | retained as TBD — official page has no 2026/27 exact dates | [VKOShP](https://nerc.itmo.ru/school/russia-team/) |
| `other:vkoshp-junior-2026` | retained as TBD — current official page has no exact cycle dates | [VKOShP.Junior](https://education.tbank.ru/school/events/vkoshp-junior/) |
| `other:mkoshp-2026` | changed — current 2026 four-stage schedule added | [MKOShP](https://mkoshp.ru/) |
| `other:yandex-cup-analytics-2026` | retained — current schedule confirmed | [Analytics](https://yandex.ru/cup/analytics) |
| `other:yandex-cup-algorithm-2026` | retained — current schedule confirmed | [Algorithm](https://yandex.ru/cup/algorithm) |
| `other:yandex-cup-machine-learning-2026` | retained — current schedule confirmed | [ML](https://yandex.ru/cup/ml) |

## Access and unresolved items

All listed official pages were reachable on 2026-09-15. PROD, Keldysh, VKOShP, and VKOShP.Junior still do not expose a current exact schedule on their official pages, so their TBD milestones remain unchanged. No dates were inferred from a prior season.
