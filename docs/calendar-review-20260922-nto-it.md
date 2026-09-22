# Calendar review — NTO and IT Olympiads

Reviewed: 2026-09-22 (Moscow).

All 46 events in `02_nto.yaml`, `08_ai_olympiads.yaml`,
`09_programming_olympiads.yaml`, `10_nto_profiles.yaml`, and
`14_yandex_cup_2026.yaml` were reviewed against organizer sources. No calendar
data change is justified by this review.

## Source findings

- The [NTO schedule](https://ntcontest.ru/participants/schedule/) is live and
  publishes senior registration 26 August–22 October 2026, stage I 17 September–23
  October, stage II from 5 November through 7 December (manual checking) or 11
  December (automatic checking), and finals in February–April 2027. It also
  confirms the junior registration, qualifier, and final windows stored in the
  calendar. Stored window `ends_at` values remain next-midnight exclusive.
- All 34 senior-profile pages listed below were opened directly and are available.
  They show profile schedule panels and say that exact profile dates are in the
  Talant personal account. Existing precise profile final dates were therefore not
  replaced with the broader central February–April range.
- The [flexible-electronics profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/flexible-electronics/)
  remains stale: its panel says 15 February–18 April **2026**. The current central
  schedule only says February–April 2027. Its stored `2027-02-01` through exclusive
  `2027-05-01` final is deliberately retained as `tentative`, sourced to the
  central schedule. This review does not claim that the profile page publishes a
  2027 final. A direct uncached `curl` retry was unavailable in the sandbox, while
  the browser result and central schedule disagree; the dated profile page was not
  allowed to overwrite the current-season central range.
- [DANO](https://dano.hse.ru/) confirms every stored date, including the project
  tour on 18–23 December (stored through exclusive 24 December). The three
  [Yandex Cup Analytics](https://yandex.ru/cup/analytics),
  [Algorithm](https://yandex.ru/cup/algorithm), and
  [ML](https://yandex.ru/cup/ml) pages confirm their stored 2026 dates and Moscow
  finals. [MKOShP](https://mkoshp.ru/) confirms all four stored rounds.
- [RUDN](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) is
  live and still confirms that both stages are remote, but its exposed dated panel
  is for the completed 2025/26 cycle. No superseding official publication was
  found, so the already-confirmed 2026/27 calendar dates are retained rather than
  removed. [PROD](https://prodcontest.com/) lists only month-level stages, and the
  [Keldysh](https://education.tbank.ru/school/olympiads/),
  [VKOShP](https://nerc.itmo.ru/school/russia-team/), and
  [VKOShP.Junior](https://education.tbank.ru/school/events/vkoshp-junior/) pages
  publish no exact future-cycle schedule; their `tbd` records remain appropriate.
- The AI Challenge landing page has little crawlable content. Its dated official
  [rules PDF](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_4LKUUtO.pdf)
  was not rendered by the browser in this pass; no superseding official dated
  source was found, so it remains the source for the stored milestones and
  parallel final/defence paths.

## Per-event disposition

Availability is the result of this review. “Retained” means dates, IDs, kinds,
status, and advancement paths were left unchanged.

| Event ID | Official source | Availability and disposition |
| --- | --- | --- |
| `nto:information-security-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-bezopasnosti/informatsionnaya-bezopasnost/) | Available; 2026/27 panel matches retained profile dates. |
| `nto:pift-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-bezopasnosti/financial-engineering/) | Available; retained. |
| `nto:big-data-machine-learning-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-po-iskusstvennomu-intellektu/bolshie-dannye-i-mashinnoe-obuchenie/) | Available; retained. |
| `nto:artificial-intelligence-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-po-iskusstvennomu-intellektu/iskusstvennyy-intellekt/) | Available; retained. |
| `nto:data-analysis-decision-making-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-po-iskusstvennomu-intellektu/analiz-dannykh-i-prinyatie-resheniy/) | Available; retained. |
| `nto-junior:iitech-2026` | [NTO Junior](https://junior.ntcontest.ru/) | Available; registration, online qualifier, and regional final windows retained. |
| `nto:automation-business-processes-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/avtomatizatsiya-bisnes-protsessov/) | Available; retained. |
| `nto:intelligent-robotic-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/intellektualnye-robototekhnicheskie-sistemy/) | Available; retained. |
| `nto:digital-sensor-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/tsifrovye-sensornye-sistemy/) | Available; retained. |
| `nto:water-robotic-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/vodnye-robototekhnicheskie-sistemy/) | Available; retained. |
| `nto:flexible-molecular-electronics-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/flexible-electronics/) / [central schedule](https://ntcontest.ru/participants/schedule/) | Available but profile final is stale 2026; retained tentative central 2027 range. |
| `nto:chemical-industrial-technologies-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-proizvodstva/khimicheskie-promtekhnologii/) | Available; retained. |
| `nto:wireless-communications-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-bezopasnosti/tekhnologii-besprovodnoy-svyazi/) | Available; retained. |
| `nto:genome-editing-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-meditsiny/genomnoe-redaktirovanie/) | Available; retained. |
| `nto:nanosystems-chemical-engineering-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-meditsiny/nanosistemy-i-khimicheskiy-inzhiniring/) | Available; retained. |
| `nto:rehabilitation-engineering-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-meditsiny/reabilitatsionnaya-inzheneriya/) | Available; retained. |
| `nto:engineering-biological-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-sredy-zhizni/inzhenernye-biologicheskie-sistemy-agrobiotekhnologii/) | Available; retained. |
| `nto:urbanistics-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-sredy-zhizni/urbanistika/) | Available; retained. |
| `nto:urban-engineering-networks-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-sredy-zhizni/ingenet/) | Available; retained. |
| `nto:modeling-biotechnologies-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-sredy-zhizni/biotech/) | Available; retained. |
| `nto:agroecological-control-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novoy-sredy-zhizni/agroekologicheskiy-kontrol/) | Available; retained. |
| `nto:infochemistry-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-po-iskusstvennomu-intellektu/infokhimiya/) | Available; retained. |
| `nto:virtual-reality-technologies-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-sozdaniya-virtualnykh-mirov/vr/) | Available; retained. |
| `nto:computer-game-development-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-sozdaniya-virtualnykh-mirov/razrabotka-komputernih-igr/) | Available; retained. |
| `nto:mobile-app-development-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-sozdaniya-virtualnykh-mirov/mobile-apps-dev/) | Available; retained. |
| `nto:intelligent-energy-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/energeticheskiy-proekt/intellektualnye-energeticheskie-sistemy/) | Available; retained. |
| `nto:nuclear-technologies-2026` | [profile](https://ntcontest.ru/tracks/nto-school/energeticheskiy-proekt/yadernye-tekhnologii/) | Available; retained. |
| `nto:quantum-engineering-2026` | [profile](https://ntcontest.ru/tracks/nto-school/energeticheskiy-proekt/kvant-ingineering/) | Available; retained. |
| `nto:chemical-power-sources-2026` | [profile](https://ntcontest.ru/tracks/nto-school/energeticheskiy-proekt/khimicheskie-istochniki-toka/) | Available; retained. |
| `nto:space-imagery-geodata-2026` | [profile](https://ntcontest.ru/tracks/nto-school/kosmicheskiy-proekt/analiz-kosmicheskikh-snimkov-i-geoprostranstvennykh-dannykh/) | Available; retained. |
| `nto:satellite-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/kosmicheskiy-proekt/sputnikovye-sistemy/) | Available; retained. |
| `nto:aerospace-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/kosmicheskiy-proekt/aerokosmicheskie-sistemy/) | Available; retained. |
| `nto:autonomous-transport-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-transporta/avtonomnye-transportnye-sistemy/) | Available; retained. |
| `nto:unmanned-aircraft-systems-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-transporta/bespilotnye-aviatsionnye-sistemy/) | Available; retained. |
| `nto:flying-robotics-2026` | [profile](https://ntcontest.ru/tracks/nto-school/proekt-novogo-transporta/letayushchaya-robototekhnika/) | Available; retained. |
| `other:ai-challenge-2026` | [rules PDF](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_4LKUUtO.pdf) | Landing page available; rules PDF was not rendered in this pass, no superseding dated source; dates and parallel terminal paths retained. |
| `other:rudn-data-analysis-machine-learning-2026` | [subject page](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie) | Available; remote format confirmed, current visible dates are prior cycle; retained. |
| `other:prod-2026` | [organizer page](https://prodcontest.com/) | Available; only month-level stages, no exact current-cycle dates; `tbd` retained. |
| `other:dano-2026` | [DANO](https://dano.hse.ru/) | Available; all stored dates and Moscow project format confirmed; retained. |
| `other:keldysh-informatics-2026` | [organizer page](https://education.tbank.ru/school/olympiads/) | Available; no future-cycle exact dates; `tbd` retained. |
| `other:vkoshp-2026` | [organizer page](https://nerc.itmo.ru/school/russia-team/) | Source endpoint was not crawlable in this review; no verified future-cycle dates; `tbd` retained. |
| `other:vkoshp-junior-2026` | [organizer page](https://education.tbank.ru/school/events/vkoshp-junior/) | Available; displayed dates are prior cycle, no future-cycle dates; `tbd` retained. |
| `other:mkoshp-2026` | [MKOShP](https://mkoshp.ru/) | Available; 26 September, 4 October, 11 October, 15 November confirmed; retained. |
| `other:yandex-cup-analytics-2026` | [Analytics](https://yandex.ru/cup/analytics) | Available; practice, qualifier, deadline, Moscow final confirmed; retained. |
| `other:yandex-cup-algorithm-2026` | [Algorithm](https://yandex.ru/cup/algorithm) | Available; practice, qualifier, deadline, Moscow final confirmed; retained. |
| `other:yandex-cup-machine-learning-2026` | [ML](https://yandex.ru/cup/ml) | Available; qualifier, deadline, Moscow final confirmed; retained. |

No IDs, milestone kinds, exclusive end dates, statuses, formats, locations, or
advancement paths were changed.
