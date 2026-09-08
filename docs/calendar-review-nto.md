# Calendar review: NTO and assigned special events

Reviewed 6 September 2026 (Europe/Moscow). Sources below are organizer or
official project pages. A `confirmed` milestone is used only where the source
states a date. For date-only ranges, the calendar's established representation
uses midnight after the source's inclusive final date as the window boundary
(for example, an official 17 September–23 October range ends at
`2026-10-24T00:00:00+03:00`). The source does not state a clock time. The NTO
and Technocup sources explicitly use Moscow time where they give it.

## `data/calendar/02_nto.yaml`

### `nto:information-security-2026`

- Official profile: [НТО — Информационная безопасность](https://ntcontest.ru/tracks/nto-school/proekt-novoy-bezopasnosti/informatsionnaya-bezopasnost/).
- The profile confirms the 2026/27 season and states: stage I, 17 September–23
  October 2026; stage II, 5 November–11 December 2026; final, 15 February–15
  April 2027. The general [NTO schedule](https://ntcontest.ru/participants/schedule/)
  independently confirms the senior-track season and gives its registration
  window as 26 August–22 October 2026.
- Changed: linked the event and its existing `:schedule` milestone to the
  profile, converted that preserved-ID milestone into the confirmed stage-I
  window, and added confirmed registration-open, registration-deadline,
  stage-II, and final milestones.

### `nto:pift-2026`

- Official profile: [НТО — Программная инженерия в финансовых технологиях](https://ntcontest.ru/tracks/nto-school/proekt-novoy-bezopasnosti/financial-engineering/).
- The profile confirms the 2026/27 dates: stage I, 17 September–23 October
  2026; stage II, 5 November–11 December 2026; final, 15 February–15 April
  2027. The [NTO schedule](https://ntcontest.ru/participants/schedule/) also
  gives the senior-track registration window as 26 August–22 October 2026.
- Changed: added confirmed registration-open and registration-deadline
  milestones. The pre-existing stage window boundaries already encode the
  source's inclusive final dates (23 October, 11 December, and 15 April) as the
  following midnight; no endpoint shift was made. Existing IDs were retained.

## `data/calendar/04_ctf_cup_russia.yaml`

### `other:ctf-cup-russia-2026`

- Official event page: [Кубок CTF России](https://ctfcup.ru/).
- The page labels the event as 2026 and gives the qualifying round as 31 October
  – 1 November.
- Verified unchanged: the source states 31 October–1 November 2026; the
  pre-existing `2026-11-02T00:00:00+03:00` boundary represents the inclusive
  final date using the calendar convention above. The page does not publish a
  clock time or timezone; the pre-existing Moscow offset is retained.

## `data/calendar/06_moscow_special_and_technocup.yaml`

## Follow-up review — 8 September 2026 (Europe/Moscow)

The entries below were checked on 8 September against the organizer pages. The
YAML importer records the check time in `source_checked_at`; calendar YAML does
not accept a separate `checked_at` field.

### Added NTO profiles

- The official [NTO senior-profile catalogue](https://ntcontest.ru/tracks/nto-school/)
  contains 34 senior profiles for 2026/27, for pupils in 8–11 classes and
  students in the first two СПО courses. Five are recorded in `02_nto.yaml`;
  the other 29, including «Разработка мобильных приложений», are recorded in
  `10_nto_profiles.yaml`. Thus every catalogue profile occurs exactly once
  across the two files.
- Added the three directly AI-related senior profiles in `02_nto.yaml`: «Большие
  данные и машинное обучение», «Искусственный интеллект», and the new «Анализ
  данных и принятие решений».
- Added NTO Junior «ИИтех» (5–7 classes). Its official
  [season page](https://junior.ntcontest.ru/) publishes registration and
  preparation, 26 August–9 November; online qualifying, 20 October–10 November;
  and regional final events, 7–17 December.
- Each remaining profile in `10_nto_profiles.yaml` now has its individual
  official URL, two registration milestones from the [NTO schedule](https://ntcontest.ru/participants/schedule/)
  (26 August and 22 October 2026), and I, II, and final milestone windows from
  that profile page. The pages label these as general periods and say that exact
  profile dates are available in the participant's personal account; this is
  reflected in every stage title. All published inclusive end dates are stored
  as the following midnight. Most profile pages give 15 February–15 April 2027
  for the final; «Гибкая и молекулярная электроника» instead literally displays
  15 February–18 April 2026, which is preserved without inferring a replacement
  year.

### Other AI competitions

- Added [AI Challenge](https://aiijc.com/) as a school-category ML competition:
  the organizer's regulations publish registration through 15 September, main
  stage through 17 September, final stage 12–26 October, and online format.
  The [official regulations](https://davmedia.cups.online/project_links/52/id_4__7bfd094e1bf00410c4998edb8d49da6e_53ao4Cd.pdf)
  also confirm registration from 25 May and defence of final solutions on 5–13 November.
  The main stage allows individual or team participation and is not marked team-only.
  The defence format is left unspecified because the regulations say it will be announced later.
- Added the RUDN profile «Анализ данных и машинное обучение» with `tbd`
  schedule only. The official [profile page](https://olympiada.rudn.ru/subject/analiz-dannyx-i-masinnoe-obucenie)
  confirms the 9–11 audience and online format but, on review, still displayed
  only the finished 2025/26 timetable. No next-cycle date was inferred.

### Rechecked special events

- [Technocup](https://techno-cup.ru/) confirms 2026/27 registration and its
  8–11 audience, but the displayed detailed timetable remains explicitly for
  2025/26. Its undated 2026/27 milestones therefore remain `tbd`.
- The official «Инженеры будущего» URL again timed out. The MISIS page for
  «Интеллектуальный мегаполис. Потенциал» still gives only 2025/26 dates. No
  special-event date was changed.

### `npk:engineers-of-the-future-2026`

- Configured official page: [Открытая городская НПК «Инженеры будущего»](https://conf.profil.mos.ru/inj/).
- Unavailable during review: the official URL timed out. Searches of the official
  domain did not yield a 2026/27 calendar. No current-season date was added; the
  event and both milestones remain `tbd`.

### `other:intellectual-megapolis-potential-2026`

- Organizer page: [НИТУ МИСИС — Интеллектуальный мегаполис. Потенциал](https://misis.ru/applicants/school-leavers/competitions/predprofessional_nyiekzamen/).
- The page confirms the contest's organizer and 11th-grade
  pre-professional audience, but publishes dates only for the concluded 2025/26
  cycle (20–21 December 2025 and 17–18 January 2026 by direction). The associated
  [MЦКО project page](https://im.mcko.ru/) likewise has no 2026/27 schedule.
- Unverified for the tracked future cycle: registration and contest dates. No
  date was added; the existing `tbd` milestones remain appropriate.

### `rsosh:technocup-2026`

- Official event page: [Технокубок](https://techno-cup.ru/).
- The current landing page confirms registration for the 2026/27 school year,
  the 8–11 grade audience, and II level of RSOSH. Its displayed detailed schedule
  is explicitly headed “25/26”; it cannot support dates for 2026/27.
- Unverified for the tracked future cycle: registration deadline, qualifiers, and
  final dates. The event remains confirmed as open for registration, while all
  undated milestones remain `tbd`. No calendar fields changed.
