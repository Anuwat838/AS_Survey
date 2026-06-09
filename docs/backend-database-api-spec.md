# AS Survey System — Backend Database + API Spec

**Prepared by:** Genos  
**Date:** 2026-06-08  
**Source blueprint:** `/opt/data/cache/documents/as_survey_system_fixed.xlsx`  
**Scope:** Backend MVP schema, import mapping, core API endpoints, validation rules

---

## 1. Recommended MVP Architecture

Use a small backend first; keep complexity low.

- **Backend:** FastAPI or Express. Genos recommendation: **FastAPI** because it is quick for JSON APIs, validation, and file uploads.
- **Database:** SQLite for MVP/dev; schema should be Postgres-compatible later.
- **File storage:** Local VPS folder for MVP, e.g. `/opt/data/as-survey-system/uploads/`.
- **Frontend:** Existing prototype can be progressively connected to APIs.
- **Import source:** Excel/Google Sheet blueprint initially, then admin UI later.

Critical decision: this system is not only a form builder. It is **survey + branch-level task tracking**.

---

## 2. Data Model

### 2.1 `users`

Stores Super Admin and AS users.

Fields:

- `id`: integer primary key
- `login_code`: text unique, required — e.g. `ADM01`, `BKK10`
- `name`: text required
- `region`: text nullable
- `phone`: text nullable
- `email`: text nullable
- `pin_hash`: text required
- `role`: text required — `super_admin`, `as`
- `status`: text required — `active`, `inactive`
- `last_login_at`: datetime nullable
- `created_at`: datetime required
- `updated_at`: datetime required

Maps from Excel:

- `AS_USERS.as_code` → `users.login_code`
- `AS_USERS.as_name` → `users.name`
- `AS_USERS.region` → `users.region`
- `AS_USERS.phone` → `users.phone`
- `AS_USERS.email` → `users.email`
- `AS_USERS.pin` → hash into `users.pin_hash`
- `AS_USERS.role` → `users.role`
- `AS_USERS.status` → `users.status`

Important: never store plain PIN in production DB.

---

### 2.2 `branches`

Master branch list.

Fields:

- `id`: integer primary key
- `branch_code`: text unique, required
- `branch_name`: text required
- `account`: text required
- `region`: text required
- `province`: text nullable
- `assigned_user_id`: FK → `users.id`, required for active branches
- `status`: text required — `active`, `inactive`
- `note`: text nullable
- `created_at`: datetime required
- `updated_at`: datetime required

Maps from Excel:

- `BRANCHES.branch_code` → `branches.branch_code`
- `BRANCHES.branch_name` → `branches.branch_name`
- `BRANCHES.account` → `branches.account`
- `BRANCHES.region` → `branches.region`
- `BRANCHES.province` → `branches.province`
- `BRANCHES.assigned_as_code` → lookup `users.login_code`, store `assigned_user_id`
- `BRANCHES.status` → `branches.status`
- `BRANCHES.note` → `branches.note`

---

### 2.3 `surveys`

Survey header.

Fields:

- `id`: integer primary key
- `survey_code`: text unique, required — e.g. `SVY-0001`
- `title`: text required
- `category`: text nullable — e.g. `AC`, `REF`, `WM`
- `description`: text nullable
- `deadline`: date required
- `status`: text required — `draft`, `published`, `closed`, `deleted`
- `created_by_user_id`: FK → `users.id`, nullable for imported data
- `created_at`: datetime required
- `published_at`: datetime nullable
- `closed_at`: datetime nullable
- `updated_at`: datetime required
- `deleted_at`: datetime nullable
- `deleted_by_user_id`: FK → `users.id`, nullable

Maps from Excel:

- `SURVEYS.survey_id` → `surveys.survey_code`
- `SURVEYS.survey_title` → `surveys.title`
- `SURVEYS.category` → `surveys.category`
- `SURVEYS.created_by` → lookup admin user if available
- `SURVEYS.created_at` → `surveys.created_at`
- `SURVEYS.published_at` → `surveys.published_at`
- `SURVEYS.deadline` → `surveys.deadline`
- `SURVEYS.closed_at` → `surveys.closed_at`
- `SURVEYS.updated_at` → `surveys.updated_at`
- `SURVEYS.status` → normalized lowercase `surveys.status`
- `SURVEYS.description` → `surveys.description`

---

### 2.4 `survey_tasks`

Branch-level tasks created when a survey is published.

Fields:

- `id`: integer primary key
- `task_code`: text unique, required — e.g. `TASK-00001`
- `survey_id`: FK → `surveys.id`, required
- `branch_id`: FK → `branches.id`, required
- `assigned_user_id`: FK → `users.id`, required
- `deadline`: date required
- `status`: text required — `new`, `pending`, `submitted`, `overdue`, `reopened`
- `assigned_at`: datetime required
- `submitted_at`: datetime nullable
- `last_updated_at`: datetime required

Constraints:

- Unique: `survey_id + branch_id`

Maps from Excel:

- `SURVEY_BRANCHES.task_id` → `survey_tasks.task_code`
- `SURVEY_BRANCHES.survey_id` → lookup `surveys.survey_code`
- `SURVEY_BRANCHES.branch_code` → lookup `branches.branch_code`
- `SURVEY_BRANCHES.assigned_as_code` → lookup `users.login_code`
- `SURVEY_BRANCHES.deadline` → `survey_tasks.deadline`
- `SURVEY_BRANCHES.task_status` → normalized lowercase `survey_tasks.status`
- `SURVEY_BRANCHES.assigned_at` → `survey_tasks.assigned_at`
- `SURVEY_BRANCHES.submitted_at` → `survey_tasks.submitted_at`
- `SURVEY_BRANCHES.last_updated_at` → `survey_tasks.last_updated_at`

---

### 2.5 `survey_questions`

Dynamic questions per survey.

Fields:

- `id`: integer primary key
- `survey_id`: FK → `surveys.id`, required
- `question_code`: text required — e.g. `Q001`
- `question_order`: integer required
- `question_text`: text required
- `answer_type`: text required — `short_text`, `long_text`, `number`, `single_choice`, `multiple_choice`, `photo`
- `required`: boolean required
- `allow_photo`: boolean required
- `photo_required`: boolean required
- `options_json`: text nullable — JSON array for choices
- `help_text`: text nullable
- `created_at`: datetime required
- `updated_at`: datetime required

Constraints:

- Unique: `survey_id + question_code`
- Unique: `survey_id + question_order`

Maps from Excel:

- `QUESTIONS.survey_id` → lookup `surveys.survey_code`
- `QUESTIONS.question_id` → `survey_questions.question_code`
- `QUESTIONS.question_order` → `survey_questions.question_order`
- `QUESTIONS.question_text` → `survey_questions.question_text`
- `QUESTIONS.answer_type` → `survey_questions.answer_type`
- `QUESTIONS.required` → boolean
- `QUESTIONS.allow_photo` → boolean
- `QUESTIONS.photo_required` → boolean
- `QUESTIONS.options` → split by `|`, store JSON
- `QUESTIONS.help_text` → `survey_questions.help_text`

---

### 2.6 `survey_responses`

One response header per task submission. A task normally has one current response; edit history can use `edit_version`.

Fields:

- `id`: integer primary key
- `response_code`: text unique, required — e.g. `RSP-00001`
- `task_id`: FK → `survey_tasks.id`, required
- `submitted_by_user_id`: FK → `users.id`, required
- `submitted_at`: datetime required
- `edit_version`: integer required default 1
- `created_at`: datetime required
- `updated_at`: datetime required

Maps from Excel:

- `RESPONSES.response_id` → `survey_responses.response_code`
- `RESPONSES.task_id` → lookup `survey_tasks.task_code`
- `RESPONSES.submitted_by` → lookup `users.login_code`
- `RESPONSES.submitted_at` → `survey_responses.submitted_at`
- `RESPONSES.edit_version` → `survey_responses.edit_version`

---

### 2.7 `survey_answers`

One answer row per response/question.

Fields:

- `id`: integer primary key
- `response_id`: FK → `survey_responses.id`, required
- `question_id`: FK → `survey_questions.id`, required
- `answer_text`: text nullable
- `answer_number`: real nullable
- `answer_json`: text nullable — for multiple choice or structured values
- `created_at`: datetime required
- `updated_at`: datetime required

Maps from Excel:

- `RESPONSES.question_id` → lookup question under the response survey
- `RESPONSES.answer_value` → store by question `answer_type`
- `RESPONSES.photo_url` → for MVP can be imported into attachment row if present

Constraint:

- Unique: `response_id + question_id`

---

### 2.8 `response_files`

Photo/file attachments.

Fields:

- `id`: integer primary key
- `file_code`: text unique, required
- `response_id`: FK → `survey_responses.id`, required
- `answer_id`: FK → `survey_answers.id`, nullable
- `survey_id`: FK → `surveys.id`, required
- `task_id`: FK → `survey_tasks.id`, required
- `branch_id`: FK → `branches.id`, required
- `question_id`: FK → `survey_questions.id`, required
- `file_name`: text required
- `file_url`: text nullable
- `file_path`: text nullable
- `file_type`: text nullable
- `uploaded_by_user_id`: FK → `users.id`, required
- `uploaded_at`: datetime required

Maps from Excel:

- `RESPONSE_FILES.file_id` → `response_files.file_code`
- `RESPONSE_FILES.response_id` → lookup response
- `RESPONSE_FILES.survey_id` → lookup survey
- `RESPONSE_FILES.branch_code` → lookup branch
- `RESPONSE_FILES.question_id` → lookup question
- `RESPONSE_FILES.file_name` → `response_files.file_name`
- `RESPONSE_FILES.file_url` → `response_files.file_url`
- `RESPONSE_FILES.file_type` → `response_files.file_type`
- `RESPONSE_FILES.uploaded_at` → `response_files.uploaded_at`
- `RESPONSE_FILES.uploaded_by` → lookup user

---

### 2.9 `status_logs`

Task status history and audit trail.

Fields:

- `id`: integer primary key
- `log_code`: text unique, required
- `task_id`: FK → `survey_tasks.id`, required
- `survey_id`: FK → `surveys.id`, required
- `branch_id`: FK → `branches.id`, required
- `old_status`: text nullable
- `new_status`: text required
- `changed_by_user_id`: FK → `users.id`, nullable
- `changed_by_code`: text nullable — keep `SYSTEM` / imported admin code if user not found
- `changed_at`: datetime required
- `note`: text nullable

Maps from Excel:

- `STATUS_LOG.log_id` → `status_logs.log_code`
- `STATUS_LOG.task_id` → lookup task
- `STATUS_LOG.survey_id` → lookup survey
- `STATUS_LOG.branch_code` → lookup branch
- `STATUS_LOG.old_status` → `status_logs.old_status`
- `STATUS_LOG.new_status` → `status_logs.new_status`
- `STATUS_LOG.changed_by` → lookup user or store as `changed_by_code`
- `STATUS_LOG.changed_at` → `status_logs.changed_at`
- `STATUS_LOG.note` → `status_logs.note`

---

### 2.10 `admin_settings`

Simple key/value settings.

Fields:

- `id`: integer primary key
- `setting_key`: text unique, required
- `setting_value`: text nullable
- `description`: text nullable
- `updated_at`: datetime required

Maps from Excel:

- `ADMIN_SETTINGS.setting_key` → `admin_settings.setting_key`
- `ADMIN_SETTINGS.setting_value` → `admin_settings.setting_value`
- `ADMIN_SETTINGS.description` → `admin_settings.description`

---

## 3. Core API Spec

Base path: `/api`

### 3.1 Auth

#### `POST /api/auth/as-login`

Request:

```json
{
  "as_code": "BKK10",
  "pin": "800250"
}
```

Response:

```json
{
  "token": "session-or-jwt-token",
  "user": {
    "id": 1,
    "login_code": "BKK10",
    "name": "MR. NOPPADON SOMSIRIPUN",
    "role": "as"
  }
}
```

Rules:

- Only active AS users can login.
- Validate PIN hash.
- AS token can only access that AS user's tasks.

#### `POST /api/auth/admin-login`

MVP can use seed admin `ADM01` + password/PIN.

---

### 3.2 Master Data

#### `GET /api/branches`

Query params:

- `account`
- `region`
- `as_code`
- `search`
- `status`

Response:

```json
{
  "items": [
    {
      "branch_code": "C5A0_2593",
      "branch_name": "BIG C (EKKAMAI)",
      "account": "BIG C",
      "region": "BANGKOK",
      "province": "BANGKOK",
      "assigned_as_code": "BKK10",
      "assigned_as_name": "MR. NOPPADON SOMSIRIPUN",
      "status": "active"
    }
  ]
}
```

#### `GET /api/filters`

Returns unique accounts, regions, AS codes for dropdowns.

---

### 3.3 Admin Survey Creation

#### `POST /api/admin/surveys`

Create draft survey.

Request:

```json
{
  "title": "ตรวจราคา Competitor AC",
  "category": "AC",
  "description": "สำรวจราคาแอร์คู่แข่งทุกสาขา",
  "deadline": "2026-06-15"
}
```

Response:

```json
{
  "survey_id": 1,
  "survey_code": "SVY-0005",
  "status": "draft"
}
```

#### `PUT /api/admin/surveys/{survey_id}`

Update draft survey info/deadline.

Rules:

- Draft survey can be edited.
- Published survey deadline can be edited only if explicitly allowed; status log should record it.

#### `POST /api/admin/surveys/{survey_id}/selected-branches`

Add branches to draft basket.

Request:

```json
{
  "branch_codes": ["C5A0_2593", "C5A0_2558"]
}
```

Response:

```json
{
  "added": 2,
  "duplicates": 0,
  "total_selected": 2
}
```

#### `GET /api/admin/surveys/{survey_id}/selected-branches`

Returns selected basket.

#### `DELETE /api/admin/surveys/{survey_id}/selected-branches/{branch_code}`

Remove one branch from basket.

---

### 3.4 Questions

#### `POST /api/admin/surveys/{survey_id}/questions`

Request:

```json
{
  "question_order": 1,
  "question_text": "ราคาแอร์ Samsung 12000 BTU (บาท)",
  "answer_type": "number",
  "required": true,
  "allow_photo": true,
  "photo_required": true,
  "options": [],
  "help_text": "ถ่ายรูปป้ายราคาแนบมาด้วย"
}
```

#### `GET /api/admin/surveys/{survey_id}/questions`

#### `PUT /api/admin/questions/{question_id}`

#### `DELETE /api/admin/questions/{question_id}`

Rules:

- Choice question requires at least one option.
- `photo_required=true` requires `allow_photo=true`.
- Questions cannot be deleted after submissions exist unless using versioning later.

---

### 3.5 Publish

#### `POST /api/admin/surveys/{survey_id}/publish`

Rules:

- Survey must have at least one selected branch.
- Every selected branch must have active assigned AS.
- Survey must have at least one question.
- Choice questions must have options.
- Creates `survey_tasks` exactly once.
- Sets survey status to `published`.

Response:

```json
{
  "survey_id": 1,
  "survey_code": "SVY-0005",
  "created_tasks": 16,
  "status": "published"
}
```

---

### 3.6 AS Tasks

#### `GET /api/as/tasks`

Auth: AS token.

Response groups tasks by survey.

```json
{
  "summary": {
    "pending": 3,
    "completed": 2,
    "overdue": 1
  },
  "surveys": [
    {
      "survey_id": 1,
      "survey_code": "SVY-0001",
      "title": "ตรวจราคา Competitor AC",
      "deadline": "2026-06-15",
      "status": "published",
      "pending_count": 3,
      "submitted_count": 1,
      "tasks": [
        {
          "task_id": 1,
          "task_code": "TASK-00001",
          "branch_code": "C5A0_2593",
          "branch_name": "BIG C (EKKAMAI)",
          "account": "BIG C",
          "region": "BANGKOK",
          "deadline": "2026-06-15",
          "status": "pending"
        }
      ]
    }
  ]
}
```

Required UX from API:

- AS tasks must be grouped by survey.
- Active and completed surveys can be separated client-side using pending count.
- Submitted tasks remain visible with View submitted.
- Deadline is included at both survey and task level.

#### `GET /api/as/tasks/{task_id}`

Returns task header + questions + current submitted response if any.

#### `POST /api/as/tasks/{task_id}/submit`

Request multipart/form-data or JSON + file uploads.

JSON shape:

```json
{
  "answers": [
    {
      "question_id": 1,
      "answer_value": "14900"
    },
    {
      "question_id": 2,
      "answer_value": "Samsung|LG"
    }
  ]
}
```

Rules:

- AS can submit only own assigned task.
- Required questions must have answers.
- Photo-required questions must have at least one uploaded file.
- On success task status becomes `submitted`.
- Submitted tasks remain queryable.

---

### 3.7 Admin Progress

#### `GET /api/admin/surveys/progress`

Returns one row/card per survey.

Fields:

- survey title
- deadline
- total assigned
- submitted
- pending
- overdue
- completion percentage
- last submitted at

#### `GET /api/admin/surveys/{survey_id}/progress`

Returns overview, by AS, pending branches, and recent submissions.

#### `GET /api/admin/surveys/{survey_id}/responses`

Returns response rows with question/answer/photo links.

#### `GET /api/admin/surveys/{survey_id}/export.xlsx`

Exports workbook sheets:

- Summary
- Pending by AS
- Pending Branches
- Responses
- Photo Links

---

### 3.8 Import

#### `POST /api/admin/import/excel`

Input: `.xlsx` blueprint.

MVP import order:

1. `AS_USERS`
2. `BRANCHES`
3. `SURVEYS`
4. `SURVEY_BRANCHES`
5. `QUESTIONS`
6. `RESPONSES`
7. `RESPONSE_FILES`
8. `STATUS_LOG`
9. `ADMIN_SETTINGS`

Response:

```json
{
  "imported": {
    "users": 2,
    "branches": 16,
    "surveys": 4,
    "tasks": 6,
    "questions": 5,
    "responses": 5,
    "files": 4,
    "status_logs": 4,
    "settings": 9
  },
  "errors": []
}
```

Import should validate references before writing, or run inside a transaction and rollback on error.

---

## 4. Validation Rules

### 4.1 Import Validation

Must reject or warn when:

- Duplicate `as_code`
- Duplicate `branch_code`
- Duplicate `survey_id`
- Duplicate `task_id`
- `BRANCHES.assigned_as_code` missing from `AS_USERS`
- `SURVEY_BRANCHES.branch_code` missing from `BRANCHES`
- `SURVEY_BRANCHES.assigned_as_code` missing from `AS_USERS`
- `QUESTIONS.survey_id` missing from `SURVEYS`
- `RESPONSES.task_id` missing from `SURVEY_BRANCHES`
- `RESPONSES.question_id` missing under the response survey
- `RESPONSE_FILES.response_id` missing from `RESPONSES`

### 4.2 Publish Validation

Block publish when:

- No selected branches
- Any branch has no active AS user
- No questions
- Choice question has no options
- `photo_required=true` while `allow_photo=false`
- Deadline is blank or invalid

### 4.3 Submit Validation

Block AS submission when:

- User does not own the task
- Task belongs to deleted/closed survey
- Required answer is missing
- Required photo is missing
- Number answer cannot be parsed as number

---

## 5. MVP Build Order

Recommended order:

1. Create backend app skeleton and SQLite DB.
2. Create tables and migrations/schema script.
3. Build Excel import validation + import.
4. Build AS login.
5. Build AS task list API.
6. Build AS task detail + submit API.
7. Build Admin progress APIs.
8. Build export API.
9. Connect existing prototype pages to APIs.

Do not start with advanced UI. The highest-risk part is reference integrity + branch-level task tracking.
