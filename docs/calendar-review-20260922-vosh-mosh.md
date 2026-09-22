# Calendar review — 22 September 2026 (Moscow)

Reviewed all 64 IDs in `01_vosh_2026.yaml`, `05_mosh_2026.yaml`, and
`06_moscow_special_and_technocup.yaml` against fresh official sources on 22
September 2026, Moscow time.

## Changes made

- **VOSH:** [`Russian`](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-russkomu-yazyku-2026-09-15)
  and [`Italian`](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-italyanskomu-yazyku-2026-09-21)
  are now `confirmed`, with their event and dated-milestone sources changed
  from the project timetable to the official announcements.  Dates did not
  change: Russian is 22 Sep and Italian is 28 Sep, each 09:00–21:00.
- **MOSH:** the required fresh full-year
  [`api/schedule?year=2026&period=year`](https://mos.olimpiada.ru/api/schedule?year=2026&period=year)
  newly lists a 5–22 Nov theoretical qualifying tour for each of engineering,
  IT, and research preprofessional profiles.  The three records changed from
  `tbd` to `confirmed`; their `ends_at` is 23 Nov 00:00, the exclusive boundary
  after the API's inclusive final day.

## Source notes

- The current VOSH [`school-stage page`](https://vos.olimpiada.ru/2026/school)
  loads its timetable with a **POST** to `/api/yearPage` (`year=2026`,
  `psevdo=school`, `textField=ds2`).  That live response contains the project
  timetable and linked project PDF.  A plain GET is intentionally not used: it
  returns an empty payload.
- Latest VOSH news visible in the current listing was dated **21 Sep**:
  Italian registration and practical-tour protocols.  The dated school-stage
  announcements used here are German (4 Sep), literature (7 Sep), home/design
  technology (8 Sep), English (9 Sep), Russian (15 Sep), technical technology
  (15 Sep), and Italian (21 Sep).  The fresh page did not expose a later dated
  registration announcement at review time.
- The current VOSH [`municipal-stage page`](https://vos.olimpiada.ru/2026/okrug)
  says preparation is under way and EКИС data collection ended 15 Sep 2026;
  its only subject-date table is explicitly headed **2025/26**.  It publishes
  no 2026/27 municipal dates.  This absence leaves existing `tbd` milestones
  intact and is not evidence against a retained event.
- MOSH's full-year feed contains eleven dated records.  The three new
  preprofessional entries above join the previously recorded physics,
  art-history, probability/statistics, astronomy, and complex-security
  milestones. The remaining financial-literacy invitational record has an inconsistent interval: start 26 Sep 2026, end 3 Nov 2025. It is not imported or used to confirm the qualifying-stage placeholder pending organizer clarification. Monthly schedule slices omit future items and were not used.
- Current NPK pages show completed **2026** material for the previous school
  year; the MИСИС page gives 20–21 Dec 2025 and 17–18 Jan 2026; neither gives
  a 2026/27 date.  [`Technocup`](https://techno-cup.ru/) invites registration
  for 2026–27 but its displayed detailed schedule is headed **25/26**.  Those
  previous-cycle dates are not applied to the 2026 records.

## Per-ID result

`confirmed` means a current official source supports the stored dated
milestone. `project` means the current VOSH project timetable supports it.
`unavailable` means the current official source publishes no date for the new
cycle, so an existing unknown/TBD milestone remains unchanged.

| ID | Result and fresh official source |
| --- | --- |
| vosh:german-2026 | confirmed — [4 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-nemetskomu-yazyku-2026-09-04); municipal unavailable. |
| vosh:literature-2026 | confirmed — [7 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-literature-2026-09-07); municipal unavailable. |
| vosh:technology-home-2026 | confirmed — [8 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-kulture-doma--dizaynu-i-tekhnologii-2026-09-08); practical 15–21 Sep; municipal unavailable. |
| vosh:technology-technical-2026 | confirmed — [15 Sep news](https://vos.olimpiada.ru/news/startoval-shkolnyy-etap-po-tekhnike--tekhnologii-i-tekhnicheskomu-tvorchestvu-2026-09-15); practical 15–21 Sep; municipal unavailable. |
| vosh:english-2026 | confirmed — [9 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-angliyskomu-yazyku-2026-09-09); municipal unavailable. |
| vosh:social-science-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:obzr-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school), including practical window; municipal unavailable. |
| vosh:russian-2026 | confirmed — [15 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-russkomu-yazyku-2026-09-15); municipal unavailable. |
| vosh:astronomy-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:physical-culture-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school), including practical window; municipal unavailable. |
| vosh:history-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:italian-2026 | confirmed — [21 Sep news](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-italyanskomu-yazyku-2026-09-21); municipal unavailable. |
| vosh:art-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:physics-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:spanish-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:informatics-robotics-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school), including practical window; municipal unavailable. |
| vosh:geography-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:biology-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:french-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:ecology-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:mathematics-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:law-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:chemistry-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:chinese-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:informatics-programming-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:informatics-security-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:economics-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| vosh:informatics-ai-2026 | project — [current school timetable](https://vos.olimpiada.ru/2026/school); municipal unavailable. |
| mosh:arabic-2026 | unavailable — profile present, no dated new-cycle item in the [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:astronomy-2026 | confirmed — 4–17 Dec; YAML exclusive end 18 Dec 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:biology-2026 | unavailable — profile present, no dated API item. |
| mosh:bioeconomics-2026 | unavailable — profile present, no dated API item. |
| mosh:probability-statistics-2026 | confirmed — 18–24 Nov; YAML exclusive end 25 Nov 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:genetics-2026 | unavailable — profile present, no dated API item. |
| mosh:geography-2026 | unavailable — profile present, no dated API item. |
| mosh:fine-art-2026 | unavailable — profile present, no dated API item. |
| mosh:informatics-10-11-2026 | unavailable — profile present, no dated API item. |
| mosh:informatics-6-9-2026 | unavailable — profile present, no dated API item. |
| mosh:information-security-2026 | unavailable — profile present, no dated API item. |
| mosh:history-2026 | unavailable — profile present, no dated API item. |
| mosh:art-history-2026 | confirmed — 14–22 Nov; YAML exclusive end 23 Nov 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:complex-security-2026 | confirmed — 12 Dec qualifier, 19 Mar 2027 theory final, 20 Mar 2027 practical final; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:linguistics-2026 | unavailable — profile present, no dated API item. |
| mosh:math-festival-2026 | unavailable — profile present, no dated API item. |
| mosh:moscow-mathematics-2026 | unavailable — profile present, no dated API item. |
| mosh:social-science-2026 | unavailable — profile present, no dated API item. |
| mosh:law-2026 | unavailable — profile present, no dated API item. |
| mosh:preprofessional-engineering-2026 | confirmed — theoretical qualifier 5–22 Nov; YAML exclusive end 23 Nov 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:preprofessional-it-2026 | confirmed — theoretical qualifier 5–22 Nov; YAML exclusive end 23 Nov 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:preprofessional-research-2026 | confirmed — theoretical qualifier 5–22 Nov; YAML exclusive end 23 Nov 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:robotics-5-8-2026 | unavailable — profile present, no dated API item. |
| mosh:robotics-9-11-2026 | unavailable — profile present, no dated API item. |
| mosh:technology-home-2026 | unavailable — profile present, no dated API item. |
| mosh:technology-technical-2026 | unavailable — profile present, no dated API item. |
| mosh:physics-2026 | confirmed — 15–22 Oct; YAML exclusive end 23 Oct 00:00; [full-year API](https://mos.olimpiada.ru/api/schedule?year=2026&period=year). |
| mosh:philology-2026 | unavailable — profile present, no dated API item. |
| mosh:financial-literacy-2026 | unavailable — profile present, no dated API item. |
| mosh:chemistry-2026 | unavailable — profile present, no dated API item. |
| mosh:ecology-2026 | unavailable — profile present, no dated API item. |
| mosh:economics-2026 | unavailable — profile present, no dated API item. |
| npk:science-for-life-2026 | unavailable — [official page](https://conf.profil.mos.ru/academ/index) has completed 2026 material only. |
| npk:engineers-of-the-future-2026 | unavailable — [official page](https://conf.profil.mos.ru/inj/) has completed 2026 material only. |
| other:intellectual-megapolis-potential-2026 | unavailable — [official MИСИС page](https://misis.ru/applicants/school-leavers/competitions/predprofessional_nyiekzamen/) gives completed 2025/26 dates only. |
| rsosh:technocup-2026 | confirmed registration; 2026/27 detailed milestones unavailable because [official page](https://techno-cup.ru/) labels its timetable 25/26. |

Raw non-versioned captures used for this review are under `/tmp/calendar-20260922-*`.
