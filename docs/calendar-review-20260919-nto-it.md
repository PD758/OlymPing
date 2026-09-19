# Calendar review — NTO and IT Olympiads

Reviewed: 2026-09-19 (Moscow).

All 46 events in `02_nto.yaml`, `08_ai_olympiads.yaml`, `09_programming_olympiads.yaml`, `10_nto_profiles.yaml`, and `14_yandex_cup_2026.yaml` were reviewed against fresh official organizer responses. Raw responses are saved in `/tmp`; paths appear below.

## Results

- The [NTO 2026/27 schedule](https://ntcontest.ru/participants/schedule/) confirms senior-track registration (26 August–22 October), stage I (17 September–23 October), stage II (5 November–11 December), and finals in February–April 2027. Inclusive windows are stored with the next midnight as their end. Its generic final range does not replace the more precise final dates already recorded for individual profiles.
- The same schedule confirms the NTO Junior online qualifier (20 October–10 November) and final (7–17 December), so the existing next-midnight ends remain correct.
- The current [AI Challenge rules](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_4LKUUtO.pdf), section 1.7, confirm: qualifier through 15 September, main stage through 17 September at 23:59 Moscow time, final 12–26 October, and defense 5–13 November. The stored progression is `qualifier → team-stage → {final, defense}`. Both final components are terminal and parallel; defense is not an invented selection after the final.
- A fresh [RUDN DA/ML page](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) confirms registration (15 September–25 January), online qualifier (1 October–25 January), and final (13–18 February). Its subject-specific final wording says distance format, which supersedes the generic `очно/дистанционно` timeline label; the recorded online final remains correct.
- Fresh [DANO](https://dano.hse.ru/), [MKOShP](https://mkoshp.ru/), and [Yandex Cup](https://yandex.ru/cup/algorithm) pages confirm their recorded dates. The three Yandex directions publish a 12–18 October practice round for Analytics/Algorithm, a 1 November qualifier for Analytics/Algorithm, a 23 October–1 November ML qualifier, and 27–29 November finals; stored inclusive windows use the next midnight.
- Fresh pages for [PROD](https://prodcontest.com/), [Keldysh](https://education.tbank.ru/school/olympiads/), [VKOShP](https://nerc.itmo.ru/school/russia-team/), and [VKOShP.Junior](https://education.tbank.ru/school/events/vkoshp-junior/) still publish no exact current-cycle schedule. Their TBD milestones are retained.

## Per-event outcomes

- `nto:information-security-2026`, `nto:pift-2026`, `nto:big-data-machine-learning-2026`, `nto:artificial-intelligence-2026`, `nto:data-analysis-decision-making-2026`, `nto-junior:iitech-2026` — retained; official NTO schedule confirms their shared applicable windows.
- `nto:automation-business-processes-2026`, `nto:intelligent-robotic-systems-2026`, `nto:digital-sensor-systems-2026`, `nto:water-robotic-systems-2026`, `nto:flexible-molecular-electronics-2026`, `nto:chemical-industrial-technologies-2026`, `nto:wireless-communications-2026`, `nto:genome-editing-2026`, `nto:nanosystems-chemical-engineering-2026`, `nto:rehabilitation-engineering-2026`, `nto:engineering-biological-systems-2026`, `nto:urbanistics-2026`, `nto:urban-engineering-networks-2026`, `nto:modeling-biotechnologies-2026`, `nto:agroecological-control-2026`, `nto:infochemistry-2026`, `nto:virtual-reality-technologies-2026`, `nto:computer-game-development-2026`, `nto:mobile-app-development-2026`, `nto:intelligent-energy-systems-2026`, `nto:nuclear-technologies-2026`, `nto:quantum-engineering-2026`, `nto:chemical-power-sources-2026`, `nto:space-imagery-geodata-2026`, `nto:satellite-systems-2026`, `nto:aerospace-systems-2026`, `nto:autonomous-transport-systems-2026`, `nto:unmanned-aircraft-systems-2026`, `nto:flying-robotics-2026` — retained; generic February–April source wording was not substituted for profile-specific dates.
- `other:ai-challenge-2026` — retained; progression, IDs, terminal fields, and dates match the current official rules.
- `other:rudn-data-analysis-machine-learning-2026` — retained; subject-specific remote-final wording controls.
- `other:prod-2026`, `other:keldysh-informatics-2026`, `other:vkoshp-2026`, `other:vkoshp-junior-2026` — retained as TBD; current official pages lack exact dates.
- `other:dano-2026`, `other:mkoshp-2026` — retained; official pages confirm stored schedule data.
- `other:yandex-cup-analytics-2026`, `other:yandex-cup-algorithm-2026`, `other:yandex-cup-machine-learning-2026` — retained; fresh current-cycle direction pages confirm stored dates.

## Saved raw sources

- `/tmp/nto_schedule_20260919.html`
- `/tmp/aichallenge_20260919.html`, `/tmp/aichallenge_rules_20260919.pdf`, `/tmp/aichallenge_rules_20260919.txt`
- `/tmp/rudn_daml_20260919.html`
- `/tmp/dano_20260919.html`, `/tmp/mkoshp_20260919.html`
- `/tmp/yandex_cup_algorithm_20260919.html`, `/tmp/yandex_cup_analytics_20260919.html`, `/tmp/yandex_cup_ml_20260919.html`
- `/tmp/prod_20260919.html`, `/tmp/tbank_olympiads_20260919.html`, `/tmp/vkoshp_20260919.html`, `/tmp/vkoshp_junior_20260919.html`
