# Проверка календарей ВсОШ и МОШ

## Допроверка 10 сентября 2026

- Проверены [лента новостей ВсОШ](https://vos.olimpiada.ru/news/count/20/page/188),
  [новость по культуре дома, дизайну и технологии](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-kulture-doma--dizaynu-i-tekhnologii-2026-09-08),
  [по технике, технологии и техническому творчеству](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-tekhnike-tekhnologii-i-tekhnicheskomu-tvorchestvu-2026-09-08)
  и [по английскому языку](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-angliyskomu-yazyku-2026-09-09).
  В `01_vosh_2026.yaml` три события (`technology-home`,
  `technology-technical`, `english`) и опубликованные школьные сроки переведены
  из `tentative` в `confirmed`. Для двух профилей труда подтверждены также
  практические туры 15–21 сентября; дальнейшие этапы сохранены `tbd`.
- В практических турах ВсОШ сохранено официально указанное время: с 09:00
  первого дня до 21:00 последнего. Для истории искусств МОШ источник называет
  только даты 14–22 ноября, поэтому окончание её окна установлено на 23 ноября
  00:00.
- [Годовое расписание МОШ](https://mos.olimpiada.ru/schedule?period=year)
  по-прежнему содержит единственную датированную запись — историю искусств.
  [Новость организатора](https://mos.olimpiada.ru/news/4596) уточняет формат
  (дистанционный) и классы (9–11): эти сведения добавлены в
  `05_mosh_2026.yaml`. Новых дат по остальным профилям не опубликовано.
- Официальные страницы [«Науки для жизни»](https://conf.profil.mos.ru/academ/index),
  [«Инженеров будущего»](https://conf.profil.mos.ru/inj/),
  [«Интеллектуального мегаполиса. Потенциала»](https://misis.ru/applicants/school-leavers/competitions/predprofessional_nyiekzamen/)
  и [«Технокубка»](https://techno-cup.ru/) проверены. Расписания НПК цикла
  2026/27 не опубликованы; на странице «Технокубка» есть регистрация на 2026/27,
  но приведённый график помечен 25/26. Поэтому даты в
  `06_moscow_special_and_technocup.yaml` не добавлялись: неизвестные этапы
  сохранены `tbd`.

## Допроверка 8 сентября 2026

- Повторно прочитан динамический график [школьного этапа ВсОШ](https://vos.olimpiada.ru/2026/school)
  через используемый страницей `/api/yearPage` (`year=2026`, `psevdo=school`, `textField=ds2`).
  Даты предметов совпадают с проверкой ниже; общий график всё ещё обозначен как проект.
- Отдельные новости подтверждают регистрацию и школьные туры по
  [немецкому языку](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-nemetskomu-yazyku-2026-09-04)
  и [литературе](https://vos.olimpiada.ru/news/otkryta-registratsiya-na-shkolnyy-etap-po-literature-2026-09-07).
  Эти два события и их опубликованные школьные даты переведены в `confirmed`;
  последующие этапы остаются `tbd`. Дедлайн регистрации не придуман из времени окончания тура.
- [Годовое расписание МОШ](https://mos.olimpiada.ru/schedule?period=year) по-прежнему
  содержит только отбор по истории искусств 14–22 ноября; [новости](https://mos.olimpiada.ru/news)
  не дали новых дат 2026/27. Остальные профили сохранены с неизвестным расписанием.
- [Кубок CTF России](https://ctfcup.ru/) по-прежнему подтверждает отбор 31 октября —
  1 ноября 2026. Изменений в `04_ctf_cup_russia.yaml` не требуется.

## Проверка 6 сентября 2026

Проверены только официальные сайты организаторов. Все время в календаре — `+03:00` (Москва).

## ВсОШ в Москве

Источник для всех 28 профилей: [страница школьного этапа 2026/27](https://vos.olimpiada.ru/2026/school) и её ссылка «Проект графика школьного этапа». Поэтому все даты сохранены как `tentative`, а не `confirmed`. Страница указывает время проведения с 09:00 первого дня до 21:00 последнего.

| Профиль | Проверенные данные школьного этапа |
| --- | --- |
| `german` | регистрация 04.09; 5–6: 11–13.09; 7–11: 11.09 |
| `literature` | 07.09; 14–16.09; 14.09 |
| `technology-home`, `technology-technical` | 08.09; теория 15–17.09 / 15.09; практика 15–21.09 |
| `english` | 09.09; 16–18.09; 16.09 |
| `social-science` | 10.09; 17–19.09; 17.09 |
| `obzr` | 14.09; теория 21–23.09 / 21.09; практика 21–27.09 |
| `russian` | 15.09; 22–24.09; 22.09 |
| `astronomy` | 16.09; 23–25.09; 23.09 |
| `physical-culture` | 17.09; теория 24–26.09 / 24.09; практика 24–30.09 |
| `history` | 18.09; 25–27.09; 25.09 |
| `italian` | 21.09; 28–30.09; 28.09 |
| `art` | 22.09; 7–11: 29.09 |
| `physics` | 23.09; 7–11: 30.09 |
| `spanish` | 24.09; 01–03.10; 01.10 |
| `informatics-robotics` | 25.09; теория 02–04.10 / 02.10; практика 02–08.10 |
| `geography` | 28.09; 05–07.10; 05.10 |
| `biology` | 29.09; 06–08.10; 06.10 |
| `french` | 30.09; 07–09.10; 07.10 |
| `ecology` | 01.10; 08–10.10; 08.10 |
| `mathematics` | 05.10; 12–15.10; 13.10 |
| `law` | 07.10; 14–16.10; 14.10 |
| `chemistry` | 08.10; 7–11: 15.10 |
| `chinese` | 09.10; 16–18.10; 16.10 |
| `informatics-programming` | 13.10; 20–22.10; 20.10 |
| `informatics-security` | 14.10; 21–23.10; 21.10 |
| `economics` | 15.10; 7–11: 22.10 |
| `informatics-ai` | 16.10; 23–25.10; 23.10 |

The table’s date order is registration; 5–6 window; 7–11 date. Every profile retains municipal, regional, and final milestones as `tbd`: no 2026/27 dates for those stages were found on this source. The four informatics profiles are mutually exclusive and the two labour profiles are mutually exclusive, as stated on the schedule.

## МОШ

The official [2026/27 schedule](https://mos.olimpiada.ru/schedule?period=year) lists all 32 tracked profiles. It had one dated item at review time; remaining profiles have no date in the full-year view and remain `tbd`. The prior-season class ranges were not treated as 2026/27 facts.

| Profiles | Coverage / limitation |
| --- | --- |
| `arabic`, `astronomy`, `biology`, `bioeconomics`, `probability-statistics`, `genetics`, `geography`, `fine-art`, `informatics-10-11`, `informatics-6-9`, `information-security`, `history`, `complex-security`, `linguistics` | Listed by the official 2026/27 schedule; date unavailable. |
| `math-festival`, `moscow-mathematics`, `social-science`, `law`, `preprofessional-engineering`, `preprofessional-it`, `preprofessional-research`, `robotics-5-8`, `robotics-9-11` | Listed by the official 2026/27 schedule; date unavailable. |
| `technology-home`, `technology-technical`, `physics`, `philology`, `financial-literacy`, `chemistry`, `ecology`, `economics` | Listed by the official 2026/27 schedule; date unavailable. |
| `art-history` | [Official profile](https://mos.olimpiada.ru/olymp/amxk) and [organizer news](https://mos.olimpiada.ru/news/4596): selection stage 14–22 November 2026, `confirmed`; the profile states that eligible grades are still being clarified. |

The MOSH schedule is dynamic and only returned the dated history-of-art item in its «до конца учебного года» view. No unavailable date has been inferred from previous years.
