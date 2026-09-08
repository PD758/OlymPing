# Release 0.2.1

The onboarding questionnaire and subject settings now offer «Вся группа ВсОШ» and
«Вся группа МОШ». Each includes all subjects from its source that pass the grade
filter, combined with individually selected subjects. Explicit source disabling and
ignored-event preferences remain effective. Existing profiles need no schema migration.

The 8 September calendar review expands the catalog to all 34 senior НТО profiles,
Junior «ИИтех», AI Challenge, the РУДН data-analysis/ML profile, «Высшая проба» industrial
programming, the Keldysh olympiad and team programming competitions. Unpublished future
schedules remain `tbd`. Existing IDs are preserved; the cancelled first qualifying
round of «Высшая проба» informatics is explicitly marked cancelled. German and literature
ВсОШ school-stage dates now have organizer confirmation.

The CLI health probe no longer imports the bot/ORM; its measured isolated peak fell
from about 198 MiB for the old import chain to 37.7 MiB for a full database/heartbeat
probe. Compose adds configurable memory limits of 384 MiB for the bot and 64 MiB for
backups. See the [memory audit](memory-audit-2026-09-08.md).

Validation: 71 tests passed; Ruff, mypy and Pyright passed; Docker Compose configuration
and frozen-lock image build passed. Repeated import of the final catalog on a copy of
the working database produced zero changes and zero notices. Calendar broadcasts still
require administrator review in `/reviews`.
