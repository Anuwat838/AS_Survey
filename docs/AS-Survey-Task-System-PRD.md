# AS Survey Task System — Product Requirement Document (PRD)

**Owner:** Armz / Super Admin  
**Prepared by:** Genos  
**Version:** v0.1 MVP Blueprint  
**Primary users:** Super Admin, AS field users  
**Initial scope:** Web survey + branch-level task tracking + Excel export

---

## 1. Executive Summary

AS Survey Task System is a private web application for assigning branch-level survey work to AS users and tracking completion by Account, Region, AS Code, and Branch. The system is intended to replace fragmented manual tracking / generic form usage with a workflow where Super Admin can select specific branches, build survey questions, publish tasks, and monitor progress until all assigned branches are submitted.

The MVP should start with **Super Admin only** on the admin side. Super Admin can see and manage all Accounts, create survey jobs, select branches through filters, build questions, publish tasks, view progress, identify incomplete AS users, and export Excel reports.

---

## 2. Problem Statement

Current survey collection through generic forms or manual follow-up has several weaknesses:

- Admin cannot easily assign survey work to selected branches only.
- AS users may not clearly see which tasks are new, pending, overdue, or completed.
- Admin cannot instantly see progress per survey.
- Admin cannot easily identify which AS still has incomplete branch tasks.
- Responses and pending lists are hard to export in a structured Account / Region / AS / Branch format.
- Photo evidence requirements vary by question and need to be controlled by admin.

The system must therefore behave as both:

1. **Survey Builder** — create question sets with answer options and photo rules.
2. **Task Management Dashboard** — track branch-level completion and pending AS users.

---

## 3. Goals

### 3.1 Business Goals

- Make survey assignment to AS users faster and more accurate.
- Reduce admin effort in tracking pending survey tasks.
- Improve visibility of incomplete work by Account, Region, AS Code, and Branch.
- Produce Excel exports that can be used for follow-up and analysis.
- Provide a foundation for future reporting, AI summaries, and automation.

### 3.2 Product Goals

- Super Admin can create a survey and assign it to selected branches.
- Branch selection supports repeated filtering and saving selected branches into a basket.
- AS users log in and see only tasks assigned to their branches.
- AS users answer survey tasks branch-by-branch.
- Admin can see survey progress and incomplete AS users clearly.
- Admin can export summary, pending, and response data to Excel.

---

## 4. Non-Goals for MVP

The MVP should avoid unnecessary complexity:

- No real-time push notification.
- No LINE/Telegram/email reminder in Phase 1.
- No advanced conditional logic in question builder.
- No AI-generated summary in Phase 1.
- No multi-admin permission splitting in Phase 1, beyond Super Admin.
- No offline mode.
- No approval/reject workflow after submission.
- No public access.

---

## 5. User Roles

## 5.1 Super Admin

Initial admin role for Phase 1.

Capabilities:

- Login to admin area.
- See all Accounts, Regions, AS Codes, Branches.
- Create survey draft.
- Select branches across filters.
- Confirm selected branches.
- Create survey questions and options.
- Configure required answers and photo attachment requirements.
- Publish survey tasks.
- See progress for every survey.
- See which AS users are incomplete.
- See pending branch list.
- View submitted responses.
- Export Excel reports.

## 5.2 AS User

Field user responsible for assigned branch survey tasks.

Login:

- Login with AS Code / Area Code, e.g. `BKK01`.
- Recommended: require PIN/password as well, not AS Code alone.

Capabilities:

- See only assigned survey tasks.
- See new, pending, submitted, and overdue tasks clearly.
- Open tasks by survey and branch.
- Submit answers per branch.
- Upload photos only when allowed/required by question.
- See completed status after submission.

---

## 6. Key Risk / Critical Decision

**Do not use AS Code alone as authentication.**

AS Code-only login is easy but weak:

- Codes can be guessed or shared.
- Anyone with the code can submit responses.
- Audit trail becomes unreliable.

MVP recommendation:

```text
AS Code + PIN
```

Examples:

```text
AS Code: BKK01
PIN: 4-6 digits
```

The system should store only `pin_hash`, never plain PIN.

---

## 7. Core Workflow Overview

## 7.1 Super Admin Survey Creation Flow

```text
Step 1: Survey Info
↓
Step 2: Branch Selection Basket
↓
Step 3: Review & Confirm Branches
↓
Step 4: Question Builder
↓
Step 5: Preview & Publish
↓
System creates branch-level survey tasks
```

## 7.2 AS Completion Flow

```text
AS login
↓
My Tasks Dashboard
↓
Select Survey
↓
Select Branch Task
↓
Answer Questions + Upload Photos if needed
↓
Submit
↓
Task status becomes Submitted
```

## 7.3 Admin Progress Flow

```text
Survey published
↓
Admin opens Survey Progress Dashboard
↓
View completion %
↓
Drill down by Account / Region / AS Code / Branch
↓
Export pending or response data
```

---

## 8. Functional Requirements

## 8.1 Authentication

### AS Login

- Input: AS Code and PIN.
- System validates active AS user.
- On success, redirect to AS My Tasks Dashboard.
- On failure, show clear error.

### Admin Login

- Super Admin login.
- Phase 1 can use username/password.
- Future: support role-based admin accounts.

Acceptance Criteria:

- AS cannot access another AS user's tasks.
- Super Admin can access all surveys and master data.
- PIN is never stored as plain text.

---

## 8.2 Master Data

Required entities:

- Accounts
- Regions
- AS Users / AS Codes
- Branches
- Branch-to-AS assignment

Each branch must have:

```text
Account
Region
AS Code / assigned user
Branch code
Branch name
Active status
```

Acceptance Criteria:

- Branches can be filtered by Account, Region, and AS Code.
- Branches without assigned AS should be flagged and blocked from publish unless fixed.

---

## 8.3 Create Survey Draft

Super Admin starts a survey by entering:

- Survey title
- Description / instruction
- Due date

The system creates a draft survey record before branch selection begins.

Reason:

- Allows selected branches to be saved as draft.
- Prevents loss if admin changes filters or refreshes page.
- Supports returning to draft later.

Acceptance Criteria:

- Draft survey is created before branch selection.
- Draft status is visible.
- Draft can be resumed before publishing.

---

## 8.4 Branch Selection Basket

This is a core MVP feature.

### Required Filter Flow

Admin selects filters in this order:

```text
Account → Region → AS Code → Branch List
```

System displays branches matching the current filters.

### Branch Selection Behavior

Admin can:

- Select individual branches with checkboxes.
- Select visible branches.
- Clear visible selection.
- Save selected branches from the current filter into a selected basket.
- Change filters and continue adding more branches.
- See total selected branches at all times.
- Remove branches from the basket.
- Review all selected branches before confirmation.

### Duplicate Handling

If the same branch is selected from multiple filters:

- Do not duplicate it.
- Show message such as: `3 branches already selected`.

### Basket Summary

Basket should show:

- Total selected branches.
- Breakdown by Account.
- Breakdown by Region.
- Breakdown by AS Code.

Acceptance Criteria:

- Changing filters does not clear the basket.
- Saved selected branches remain in draft.
- Duplicate branch IDs are not added twice.
- Admin can review all selected branches before proceeding.

---

## 8.5 Review & Confirm Branches

Before setting questions, Super Admin must review selected branches.

Review page shows:

- Account
- Region
- AS Code
- Branch code
- Branch name

Summary shows:

- Total selected branches
- Number of Accounts
- Number of Regions
- Number of AS Codes

Actions:

- Back to edit selection
- Confirm branch selection

Acceptance Criteria:

- Survey cannot proceed to question builder without at least 1 selected branch.
- Survey cannot be published if any selected branch has no assigned AS.

---

## 8.6 Question Builder

Super Admin can create survey questions after confirming branches.

### MVP Question Types

- Short text
- Long text
- Number
- Single choice
- Multiple choice
- Photo

### Question Settings

Each question supports:

- Question text
- Question type
- Required answer: yes/no
- Allow photo: yes/no
- Photo required: yes/no
- Options for choice questions
- Display order

### Photo Rules

Photo attachment is not required on every question. Admin can control this per question:

- `allow_photo = false` → no photo upload field.
- `allow_photo = true` and `photo_required = false` → optional photo.
- `photo_required = true` → AS must upload photo before submit.

Acceptance Criteria:

- Choice questions require at least 1 option before publish.
- Required questions must be answered by AS.
- Photo-required questions block submit until a photo is uploaded.

---

## 8.7 Preview & Publish

Before publish, Super Admin sees:

- Survey info
- Selected branch count
- Question list
- AS-side preview

When published:

- System creates `survey_tasks` for each selected branch.
- Each task is assigned to the AS user responsible for that branch.
- Survey status becomes `published`.
- AS users see the tasks after login.

Acceptance Criteria:

- Tasks are created only at publish time.
- Draft selected branches do not create active AS tasks.
- Published survey cannot be accidentally edited in a way that corrupts submitted answers.

---

## 8.8 AS My Tasks Dashboard

AS sees a clear task dashboard after login.

Required display:

- New tasks
- Pending tasks
- Overdue tasks
- Submitted tasks
- Grouped by Account and Survey

Each survey card shows:

- Survey title
- Account
- Due date
- Pending branch count
- Submitted branch count

Each branch task shows:

- Branch code
- Branch name
- Region
- Status

Acceptance Criteria:

- AS sees only tasks assigned to their user ID.
- AS can identify unfinished work immediately.
- Submitted tasks are visually distinct from pending tasks.

---

## 8.9 AS Survey Submission

For each branch task, AS opens a survey form.

Header must show:

- Survey title
- Account
- Region
- Branch code/name
- Due date

Submission behavior:

- AS answers all required questions.
- AS uploads photos where required.
- AS submits the branch task.
- Task status changes to `submitted`.
- `submitted_at` is recorded.

Acceptance Criteria:

- Required validation is enforced.
- Photo validation is enforced.
- After submit, admin progress updates.

---

## 8.10 Survey Progress Dashboard

This is a must-have MVP admin feature.

Super Admin sees every published survey and progress status.

### Survey List Cards

Each survey card shows:

- Survey title
- Account scope
- Due date
- Status: Draft / Active / Closed / Overdue
- Total assigned branches
- Submitted branches
- Pending branches
- Completion percentage
- Last submitted at

Progress calculation:

```text
Completion % = submitted tasks / total assigned tasks × 100
```

Acceptance Criteria:

- Progress is based on branch-level tasks, not AS count.
- Completion updates after every submitted task.

---

## 8.11 Survey Progress Detail

Each survey has a progress detail page.

Recommended tabs:

1. Overview
2. By AS
3. By Region
4. Pending Branches
5. Responses

### Overview Tab

Shows:

- Total assigned
- Submitted
- Pending
- Overdue
- Completion %
- Progress by Account
- Progress by Region
- Recent submissions

### By AS Tab

Shows:

- AS Code
- AS Name
- Assigned branches
- Submitted branches
- Pending branches
- Completion %
- Last submitted at

Definition of incomplete AS:

```text
AS is incomplete if they have at least 1 pending branch task for that survey.
```

### Pending Branches Tab

Shows all unfinished tasks:

- AS Code
- AS Name
- Account
- Region
- Branch code
- Branch name
- Due date
- Status: Pending / Overdue

Acceptance Criteria:

- Admin can identify incomplete AS users in each survey.
- Admin can drill down to exact pending branches.
- Admin can filter only incomplete AS.

---

## 8.12 Excel Export

Required export types:

### Survey Progress Summary

Columns:

- Survey title
- Account
- Due date
- Total assigned
- Submitted
- Pending
- Completion %

### Pending by AS

Columns:

- Survey title
- AS Code
- AS Name
- Assigned
- Submitted
- Pending
- Completion %

### Pending Branches

Columns:

- Survey title
- Account
- Region
- AS Code
- AS Name
- Branch code
- Branch name
- Status
- Due date

### Survey Responses

Columns:

- Survey title
- Account
- Region
- AS Code
- Branch code
- Branch name
- Question
- Answer
- Photo link/path
- Submitted at

Recommended workbook sheets:

- Summary
- Pending by AS
- Pending Branches
- Responses
- Photo Links

Acceptance Criteria:

- Exports open correctly in Excel.
- Thai text remains readable.
- Response export includes photo references.


---

## 8.13 Multiple Survey Progress Dashboard

When multiple surveys are active at the same time, Super Admin must see progress separately for each survey. Progress must never be merged across different surveys.

### Survey Progress List

The Progress Dashboard should show a list/table/card view of all surveys:

- Survey title
- Due date
- Status: Draft / Active / Overdue / Closed
- Total assigned branches
- Submitted branches
- Pending branches
- Overdue branches
- Completion percentage
- Last submitted at
- Actions: View detail, Export, Delete

### Required Behavior

- Each survey calculates completion from its own `survey_tasks` only.
- The same branch can have tasks in multiple surveys.
- Admin can open each survey to view detail breakdown by AS, Region, Pending Branches, and Responses.

Acceptance Criteria:

- If 3 surveys are active, the dashboard shows 3 separate progress rows/cards.
- Completion percentage for Survey A is not affected by Survey B or C.
- Admin can identify which surveys are most incomplete at a glance.

---

## 8.14 Delete Survey

Super Admin must be able to delete a survey even if the survey is not complete. Because this action can destroy task and response records, deletion must require explicit confirmation with the admin password.

### Delete Scope

MVP recommendation:

- Allow delete for Draft surveys.
- Allow delete for Published surveys only after password confirmation.
- Deleted surveys should preferably be soft-deleted first, not physically removed from database immediately.

### Delete Confirmation Flow

When Super Admin clicks Delete:

1. Show warning modal.
2. Display survey title, assigned count, submitted count, and pending count.
3. Require Super Admin to type admin password.
4. Require an explicit confirmation button: `Delete survey permanently`.
5. Record audit log.
6. Hide deleted survey from normal dashboards.

### Recommended Data Handling

Use soft delete in MVP:

```text
surveys.deleted_at
surveys.deleted_by
surveys.delete_reason optional
```

Do not immediately hard-delete uploaded photos and responses unless storage cleanup is intentionally implemented.

### Audit Log

Record:

- survey_id
- survey_title
- deleted_by
- deleted_at
- assigned task count
- submitted task count
- pending task count

Acceptance Criteria:

- Admin cannot delete survey without password confirmation.
- Delete warning clearly states if the survey has submitted responses.
- Deleted survey no longer appears in active progress dashboard.
- Deleted survey action is auditable.

---

## 9. Data Model Draft

## 9.1 users

```text
id
login_code        e.g. BKK01
pin_hash
name
role              super_admin / as
active
created_at
updated_at
```

## 9.2 accounts

```text
id
name
active
```

## 9.3 regions

```text
id
name
active
```

## 9.4 branches

```text
id
account_id
region_id
branch_code
branch_name
active
```

## 9.5 user_branch_assignments

```text
id
user_id
branch_id
active
created_at
```

## 9.6 surveys

```text
id
title
description
due_date
status            draft / branches_confirmed / questions_ready / published / closed
created_by
created_at
updated_at
published_at
deleted_at
deleted_by
```

## 9.7 survey_selected_branches

Stores draft/confirmed selected branches before publish.

```text
id
survey_id
branch_id
selected_by
selected_at
confirmed_at
```

Unique constraint:

```text
survey_id + branch_id
```

## 9.8 survey_questions

```text
id
survey_id
question_text
question_type     short_text / long_text / number / single_choice / multiple_choice / photo
required
allow_photo
photo_required
display_order
```

## 9.9 survey_options

```text
id
question_id
option_text
display_order
```

## 9.10 survey_tasks

Created only on publish.

```text
id
survey_id
branch_id
assigned_user_id
status            pending / submitted
assigned_at
due_date
submitted_at
```

## 9.11 survey_responses

```text
id
task_id
submitted_by
submitted_at
```

## 9.12 survey_answers

```text
id
response_id
question_id
answer_text
answer_number
answer_json
```

## 9.13 survey_attachments

```text
id
answer_id
file_path
original_filename
uploaded_at
```


## 9.14 audit_logs

```text
id
actor_user_id
action              e.g. delete_survey
entity_type         survey
entity_id
metadata_json
created_at
```

---

## 10. Status Rules

## Survey Status

```text
Draft
Branches Confirmed
Questions Ready
Published / Active
Closed
```

## Task Status

Stored values:

```text
pending
submitted
```

Derived values:

```text
new       = pending and recently created
overdue   = pending and now > due_date
completed = submitted
```

---

## 11. MVP Screens

## Super Admin

1. Admin Login
2. Survey List / Progress Dashboard
3. Create Survey Info
4. Branch Selection Basket
5. Review Selected Branches
6. Question Builder
7. Preview & Publish
8. Survey Progress Detail
9. Export Center

## AS User

1. AS Login
2. My Tasks Dashboard
3. Survey Branch Task List
4. Survey Form
5. Submission Success

---

## 12. UX Requirements

## 12.1 Admin UX

Admin screens should prioritize clarity and tracking:

- Desktop-first.
- Data-dense but readable.
- Persistent selected branch basket during branch selection.
- Clear progress bars and status badges.
- Fast filtering by Account / Region / AS Code.
- Export buttons visible on progress pages.

## 12.2 AS UX

AS screens should be mobile-first:

- Large task cards.
- Clear pending count.
- Account and survey grouping.
- Minimal typing.
- Simple photo upload.
- Obvious submit state.

---

## 13. Security and Privacy

- Require authentication for every page.
- Use AS Code + PIN, not AS Code alone.
- Store PIN as hash.
- Restrict AS visibility to assigned tasks only.
- Restrict uploaded file access to authenticated users.
- Keep admin actions audited.
- Validate file type and size for uploads.

---

## 14. MVP Acceptance Criteria Summary

The MVP is acceptable when:

- Super Admin can create a survey draft.
- Super Admin can select branches through Account → Region → AS Code filters.
- Selected branches remain saved across filter changes.
- Super Admin can review and confirm selected branches.
- Super Admin can create questions with options and photo settings.
- Publishing creates branch-level tasks for selected branches only.
- AS users can login and see assigned tasks.
- AS users can submit branch-level responses.
- Super Admin can see progress percentage for each survey.
- Super Admin can see incomplete AS users per survey.
- Super Admin can see exact pending branch list.
- Super Admin can export Excel reports.

---

## 15. Recommended Build Phases

## Phase 1 — MVP

- Auth: Super Admin + AS Code/PIN.
- Master data seed/import.
- Survey draft creation.
- Branch selection basket.
- Question builder.
- Publish tasks.
- AS task dashboard and submission.
- Admin progress dashboard.
- Excel export.

## Phase 2 — Operations Improvement

- Bulk import users/branches.
- Save branch selection templates.
- Better image compression/preview.
- Close/reopen survey.
- Edit draft questions before publish.
- Export formatting improvements.

## Phase 3 — Automation and Intelligence

- Reminder notification.
- Telegram/LINE/email follow-up.
- AI summary by Account/Region/AS.
- Research Hub integration.
- Competitor price analysis reports.
- Approval/reject response workflow.

---

## 16. Open Decisions

1. Confirm whether AS Code + PIN is accepted instead of AS Code alone.
2. Decide whether AS can edit submitted answers in MVP.
3. Decide file storage approach: local VPS storage vs S3-compatible storage.
4. Decide if master data is imported from Excel or managed in admin UI first.
5. Decide whether surveys can cover multiple Accounts in one survey, or one survey per Account only.

---

## 17. Genos Recommendation

Start with the branch selection + progress tracking core before adding advanced survey logic. The strongest differentiator versus Google Form is not question creation; it is controlled branch assignment and completion visibility by AS.

Recommended immediate next artifact:

```text
Clickable HTML prototype:
1. Branch Selection Basket
2. Review Selected Branches
3. Question Builder
4. Survey Progress Detail
```
