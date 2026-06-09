# AS Survey Workbook V.2 Validation / Master Import Report

File:

```text
/opt/data/cache/documents/doc_532d55c55b7e_as_survey_system_fixed V.2.xlsx
```

## Safe summary

- File is a valid XLSX workbook.
- Workbook validation: valid.
- Excel error tokens: none.
- AS users: 59
- Unique AS codes: 59
- Branches: 504
- AS codes assigned to branches: 59
- Branches per AS: min 3, max 13
- Surveys in workbook: 0
- Survey tasks in workbook: 0
- Questions in workbook: 0

## Fixed issues confirmed

Previous bad region is fixed:

```text
branch_code: C070210091
branch_name: LOTUS (SI RACHA)
region: CENTRAL
province: CHON BURI
assigned_as_code: CT05
```

CT02 was patched in live DB from inactive to active after backup:

```text
backup: /opt/data/as-survey-system/backups/as-survey-backup-20260609_033748
CT02 status: active
CT02 assigned branches: 6
```

## Master-data-only import result

Master-data-only import was run with a pre-import backup:

```text
/opt/data/as-survey-system/backups/as-survey-import-backup-20260609_032103
```

Imported:

- AS users: 59
- Branches: 504
- Admin settings: 9

Post-import live DB counts:

- users: 60
- AS users: 59 active
- super admins: 1
- branches: 504
- surveys preserved: 4
- survey tasks preserved: 6
- survey questions preserved: 5
- survey responses preserved: 8
- response files preserved: 8
- admin settings: 9
- bad region token count: 0
- Admin default PIN: false

## Pilot smoke test result after CT02 patch

A temporary CSV was generated from workbook AS code/PIN values, used for smoke testing, then deleted.

Smoke test:

```text
checked_users: 59
passed: 59
failed: 0
min_task_count: 0
max_task_count: 6
```

Backend health:

```text
{"ok": true}
```

## Important readiness note

Login smoke is fully passing, but current survey task coverage is still sample/demo-sized:

```text
active AS users: 59
branches: 504
survey_tasks: 6
AS users with at least one task: 1
```

Before sending links for a real data collection round, create/publish the actual survey and generate tasks for the target branches/AS users.

## Security note

This report intentionally does not include any PIN values.
