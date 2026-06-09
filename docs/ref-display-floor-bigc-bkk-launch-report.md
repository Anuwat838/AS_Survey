# Survey Launch Report — REF Display on Floor / Big C BKK

Created at: 2026-06-09

## Requested survey

- Title: ตรวจนับจำนวน Display on Floor
- CAT: REF
- Deadline: 2026-06-15
- Question: จำนวน ตู้เย็น ที่วาง Display on Floor ปัจจุบัน
- Answer type: number
- Photo: allowed, not required
- Scope: account Big C / region BKK

## Scope interpretation

Database region values split BKK into:

- BANGKOK
- BANGKOK METROPOLIS

For this launch, BKK was interpreted as both `BANGKOK` and `BANGKOK METROPOLIS`, because both are assigned to BKK AS codes.

## Backup before creation

```text
/opt/data/as-survey-system/backups/as-survey-backup-20260609_043258
```

## Created survey

```text
survey_id: 9
survey_code: REF-DOF-BIGC-BKK-20260615
title: ตรวจนับจำนวน Display on Floor
category: REF
deadline: 2026-06-15
status: published
```

## Created question

```text
question_code: REF_DISPLAY_ON_FLOOR_COUNT
question_order: 1
question_text: จำนวน ตู้เย็น ที่วาง Display on Floor ปัจจุบัน
answer_type: number
required: true
allow_photo: true
photo_required: false
```

## Created tasks

- Total selected branches: 52
- Total tasks: 52
- Assigned AS users: 13
- Region distribution:
  - BANGKOK: 34
  - BANGKOK METROPOLIS: 18
- Scope mismatch count: 0

## Task distribution by AS

- BKK01: 6
- BKK02: 6
- BKK03: 1
- BKK04: 3
- BKK05: 6
- BKK06: 4
- BKK07: 6
- BKK08: 3
- BKK09: 2
- BKK10: 5
- BKK11: 2
- BKK12: 6
- BKK13: 2

## Verification

Backend health:

```text
{"ok": true}
```

Admin progress view:

```text
total_assigned: 52
submitted_count: 0
pending_count: 52
completion_pct: 0.0
```

AS API visibility smoke:

```text
checked_as: 13
all_ok: true
```

Each assigned AS can login, sees the new survey, sees their task count, and task detail returns the number question with optional photo enabled.

## Launch note

Ready to send survey communication to BKK AS users BKK01-BKK13 only.

Security note: this report intentionally does not include PIN values.
