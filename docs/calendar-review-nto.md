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
