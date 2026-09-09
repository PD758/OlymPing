# Calendar review: Международная олимпиада по финансовой безопасности

Reviewed 8 September 2026 (Europe/Moscow). This review records the 2026 season
that the organizer currently publishes; it does not infer registration or dates
for a later cycle.

## `data/calendar/13_rosfin_olympiad.yaml`

- Official [participant page](https://rosfinolymp.ru/for-participants) names
  the school profile «финансовая безопасность». It admits pupils in grades 8–10
  at the qualifying round, and lists mathematics, informatics, and social
  studies as its school-subject basis. The same page lists economics and law
  only among the separate university-student training directions, so the school
  event has `financial-literacy` only, without `economics` or `law` tags.
- The official [stage schedule](https://rosfinolymp.ru/stages) gives the
  school-specific online dates as 14 March for round 1 and 19 April for round
  2. Its broad 14–17 March and 19–21 April labels cover other participant
  groups too and were not used as the school-stage dates. The page also gives
  the school qualification milestones: motivation letters, 1 June–2 September;
  selection, 2–3 September.
- Round 2 has a confirmed common school window of 10:00–14:00 MSK on 19 April.
  Round 1 times vary by grade and are recorded in the description rather than
  represented as one common start time.
- The organizer publishes the final as 27 September–2 October 2026. It also
  labels the school tasks by grades 9, 10, and 11. The final milestone and the
  event description explicitly say it is for participants who passed selection;
  it is not represented as an open registration opportunity.
- The remaining multi-day ranges have no clock time. Each inclusive range is stored
  as a `window` ending at the following midnight with the established Moscow
  offset (`+03:00`): 2 September becomes 3 September, 3 September becomes 4
  September, and 2 October becomes 3 October. The source warns that dates can
  be clarified in participants' personal accounts.

## Progression correction — 9 September 2026

The stage dates were present but their progression links were missing, producing three
administrator gap alerts. Added round 1 → round 2 → qualification selection → final.
The motivation-letter window also depends on round 2; it is an auxiliary `other` milestone,
not a separately graded prerequisite requiring a fictional “passed” result.

Checked the [2026 regulations linked by the organizer](https://rosfinolymp.ru/documents):
section 2.9 confirms advancement from round 1 to round 2; sections 2.12–2.16 describe
documents, consent and the motivation essay for qualification. A “passed” qualification
result represents actual admission to the final, not merely uploading a letter.
The [official stage schedule](https://rosfinolymp.ru/stages) supplies all continuation dates.
No dates or application version changed. Importing this correction resolves the existing
gap records automatically on the next notification cycle.
