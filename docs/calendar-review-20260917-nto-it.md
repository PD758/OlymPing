# Calendar review — NTO and IT Olympiads

Reviewed: 2026-09-17 (Moscow).

All 46 events in `02_nto.yaml`, `08_ai_olympiads.yaml`, `09_programming_olympiads.yaml`, `10_nto_profiles.yaml`, and `14_yandex_cup_2026.yaml` were checked against the current official pages below. Raw responses were saved for independent review in `/tmp` with the paths listed in [Saved raw sources](#saved-raw-sources).

## Changes

- The [NTO 2026/27 schedule](https://ntcontest.ru/participants/schedule/) confirms the stored senior-track windows: Stage I 17 September–23 October, Stage II 5 November–11 December (the next-midnight stored end is 12 December), and finals in February–April. The site provides no profile-specific final dates, so its shared month range did not replace the existing more-specific 15 February–15 April profile windows.
- The same NTO schedule confirms Junior's online qualifier (20 October–10 November) and final (7–17 December); stored next-midnight end dates remain correct.
- The current [AI Challenge 2026 rules](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_4LKUUtO.pdf), section 1.7, makes all stages mandatory: qualification results move participants to the main stage; main-stage results determine finalists; finalists complete the final and defend its solution. The existing IDs now carry `qualifier → team-stage → final` and `qualifier → team-stage → defense` progression links. Defense is a mandatory component of the final, rather than a selection after it, so both final milestones have the same main-stage admission path. Qualification (1 June–15 September) and main stage (1 July–17 September) deliberately overlap according to the same rule, so no date-order assumption was made.
- A fresh direct fetch of the [RUDN DA/ML page](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) confirms the current 2026/27 registration, qualifier, and final dates. The generic timeline says “очно/дистанционно”, while the subject-specific final section says it is distance format; the subject-specific wording prevails, so the stored online final was retained.
- [DANO](https://dano.hse.ru/), [MKOShP](https://mkoshp.ru/), and the three current [Yandex Cup](https://yandex.ru/cup/algorithm) direction pages support the dates already recorded. Yandex Cup source pages expose the 2026 schedule; no date was taken from their archived 2025 material.
- [PROD](https://prodcontest.com/), [Keldysh](https://education.tbank.ru/school/olympiads/), [VKOShP](https://nerc.itmo.ru/school/russia-team/), and [VKOShP.Junior](https://education.tbank.ru/school/events/vkoshp-junior/) still provide no exact current-cycle dates, so their TBD milestones remain intact. An unavailable or stale page was never used to invalidate dates.

## Event outcomes

The following IDs were retained with their recorded dates, milestone IDs, progression paths, and terminal fields:

- `nto:information-security-2026`, `nto:pift-2026`, `nto:big-data-machine-learning-2026`, `nto:artificial-intelligence-2026`, `nto:data-analysis-decision-making-2026`, `nto-junior:iitech-2026` — [NTO schedule](https://ntcontest.ru/participants/schedule/).
- `nto:automation-business-processes-2026`, `nto:intelligent-robotic-systems-2026`, `nto:digital-sensor-systems-2026`, `nto:water-robotic-systems-2026`, `nto:flexible-molecular-electronics-2026`, `nto:chemical-industrial-technologies-2026`, `nto:wireless-communications-2026`, `nto:genome-editing-2026`, `nto:nanosystems-chemical-engineering-2026`, `nto:rehabilitation-engineering-2026`, `nto:engineering-biological-systems-2026`, `nto:urbanistics-2026`, `nto:urban-engineering-networks-2026`, `nto:modeling-biotechnologies-2026`, `nto:agroecological-control-2026`, `nto:infochemistry-2026`, `nto:virtual-reality-technologies-2026`, `nto:computer-game-development-2026`, `nto:mobile-app-development-2026`, `nto:intelligent-energy-systems-2026`, `nto:nuclear-technologies-2026`, `nto:quantum-engineering-2026`, `nto:chemical-power-sources-2026`, `nto:space-imagery-geodata-2026`, `nto:satellite-systems-2026`, `nto:aerospace-systems-2026`, `nto:autonomous-transport-systems-2026`, `nto:unmanned-aircraft-systems-2026`, `nto:flying-robotics-2026` — [NTO schedule](https://ntcontest.ru/participants/schedule/); the shared final-month range was not substituted for existing profile windows.
- `other:ai-challenge-2026` — changed only to add documented progression paths and current official rules URLs; dates and IDs retained.
- `other:rudn-data-analysis-machine-learning-2026` — current 2026/27 dates and subject-specific distance format retained.
- `other:prod-2026`, `other:keldysh-informatics-2026`, `other:vkoshp-2026`, `other:vkoshp-junior-2026` — retained as TBD because no exact current-cycle date is published by the organizer.
- `other:dano-2026` — retained — [official schedule](https://dano.hse.ru/).
- `other:mkoshp-2026` — retained — [official 2026 rules and schedule](https://mkoshp.ru/); existing `:schedule` ID preserved.
- `other:yandex-cup-analytics-2026`, `other:yandex-cup-algorithm-2026`, `other:yandex-cup-machine-learning-2026` — retained — [current Yandex Cup directions](https://yandex.ru/cup/algorithm).

## Saved raw sources

- `/tmp/nto_schedule_20260917.html` — NTO official schedule.
- `/tmp/aiijc_20260917.html`, `/tmp/aiijc_main_stage_faq_20260917.html` — AI Challenge current site responses.
- `/tmp/aichallenge_rules_20260917.pdf` and `/tmp/aichallenge_rules_20260917.txt` — AI Challenge 2026 rules used for dates and progression.
- `/tmp/rudn_daml_20260917.html` — freshly fetched RUDN 2026/27 page.
- `/tmp/dano_20260917.html`, `/tmp/mkoshp_20260917.html` — DANO and MKOShP official pages.
- `/tmp/yandex_cup_algorithm_20260917.html`, `/tmp/yandex_cup_analytics_20260917.html`, `/tmp/yandex_cup_ml_20260917.html` — current Yandex Cup direction pages.
- `/tmp/prod_20260917.html`, `/tmp/tbank_olympiads_20260917.html`, `/tmp/vkoshp_20260917.html`, `/tmp/vkoshp_junior_20260917.html` — current pages used to retain the four incomplete-schedule events as TBD.
