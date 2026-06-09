# AS Survey System Production Roadmap

> เจ้าของงาน: Armz  
> Technical lead: Genos  
> สถานะปัจจุบัน: Backend MVP รันได้แล้วบน FastAPI + SQLite port 8030

## Goal

ทำให้ระบบ AS Survey จาก prototype + backend MVP กลายเป็นระบบที่ user ใช้งานจริงได้ ตั้งแต่ Admin สร้าง/นำเข้า survey, AS login ดูงาน/ส่งคำตอบพร้อมรูป, Admin ติดตามงาน/export report, จนถึง deploy แบบปลอดภัยและดูแลต่อได้

## หลักการนำทาง

1. Genos เป็นคนนำด้าน backend/technical architecture
2. Armz ตัดสินใจเฉพาะ business rule, flow หน้างาน, ข้อความในระบบ, และ approval เรื่องความเสี่ยง/ค่าใช้จ่าย/public exposure
3. ทำทีละ milestone ที่ทดสอบได้ ไม่ build ใหญ่ทีเดียว
4. ทุก milestone ต้องมี test หรือ checklist ก่อนถือว่าเสร็จ
5. หลีกเลี่ยง paid API และ cloud service ใหม่จนกว่า Armz อนุมัติ

---

## Phase 0 — Current MVP Baseline

สถานะ: Done

สิ่งที่มีแล้ว:

- Backend root: `/opt/data/as-survey-system/backend`
- DB: `/opt/data/as-survey-system/backend/as_survey.db`
- API docs: `http://localhost:8030/docs` ผ่าน SSH tunnel
- Excel import จาก `/opt/data/cache/documents/as_survey_system_fixed.xlsx`
- AS/Admin login
- AS task list grouped by survey
- AS submit API แบบ JSON + photo URL
- Admin progress/import APIs
- Test suite: `9 passed`

ข้อจำกัดปัจจุบัน:

- ยังเป็น dev server
- token ยังเก็บใน memory
- Admin PIN test เป็น `0000`
- ยังไม่มี frontend ต่อ API จริง
- upload รูปจริงยังไม่ production-ready
- ยังไม่มี backup/deploy/security hardening

---

## Confirmed Product Decisions

- Visual tone: Minimal, lots of whitespace, thin borders, soft shadows, no heavy gradients.
- Pilot size: 2 AS users.
- Photo limit: maximum 5 photos per question.

---

## Phase 1 — Connect Prototype UI to Backend API

เป้าหมาย: ให้ Armz และ user เห็น flow จริงบนหน้าเว็บ ไม่ใช่ mock data

งานหลัก:

1. แยก config API base URL ใน prototype
2. ต่อ AS login เข้ากับ `/api/auth/as-login`
3. เก็บ token ใน browser แบบ dev-safe
4. ต่อหน้า AS task list เข้ากับ `/api/as/tasks`
5. ต่อ task detail เข้ากับ `/api/as/tasks/{task_id}`
6. ต่อ submit form เข้ากับ `/api/as/tasks/{task_id}/submit`
7. ต่อ Admin login เข้ากับ `/api/auth/admin-login`
8. ต่อ Admin progress dashboard เข้ากับ `/api/admin/surveys/progress`
9. เพิ่ม loading/error state ภาษาไทย
10. ทดสอบ flow จาก browser จริง

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- ข้อความ error ภาษาไทยที่อยากให้ AS เห็น เช่น PIN ผิด, งานหมดอายุ, ส่งไม่ครบ
- หน้าตา UI prototype เดิมโอเคไหม หรืออยากปรับ layout ก่อนต่อ API

Definition of Done:

- AS login ได้จากหน้าเว็บ
- AS เห็นเฉพาะงานตัวเอง
- AS ส่งคำตอบได้อย่างน้อย 1 task
- Admin เห็น progress เปลี่ยนหลัง AS submit

---

## Phase 2 — Admin Survey Management MVP

เป้าหมาย: Admin ไม่ต้องพึ่ง Excel อย่างเดียว เริ่มจัดการ survey ในระบบได้

งานหลัก:

1. Admin ดูรายการ surveys ทั้งหมด
2. Admin ดูรายละเอียด survey
3. Admin สร้าง survey draft ใหม่
4. Admin เพิ่ม/แก้คำถาม
5. Admin เลือก branch ที่ต้องการ assign
6. Admin ตั้ง deadline
7. Admin publish survey แล้วระบบสร้าง tasks
8. Admin close survey ได้
9. เพิ่ม validation ก่อน publish เช่น ต้องมี deadline, branch, question

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- Admin มีคนเดียวหรือหลายคน
- Survey category ต้อง fix เป็น REF/WM/AC หรือเปิด custom
- Deadline เป็นราย survey อย่างเดียว หรือแยก deadline ราย branch ได้ด้วย

Definition of Done:

- Admin สร้าง survey จากเว็บได้โดยไม่ต้องแก้ Excel
- AS เห็น task ใหม่หลัง publish
- Admin ปิด survey ได้

---

## Phase 3 — Real Photo Upload

เป้าหมาย: AS ส่งรูปจากมือถือ/เว็บได้จริง

งานหลัก:

1. เพิ่ม upload endpoint แบบ multipart
2. เก็บไฟล์ใน local uploads folder
3. สร้าง path แยกตาม survey/task/question
4. จำกัดชนิดไฟล์เฉพาะ image
5. จำกัดขนาดไฟล์
6. บันทึก metadata ใน `response_files`
7. แสดง preview รูปใน AS submitted view
8. แสดงรูปใน Admin response view

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- รูป 1 คำถามให้แนบได้สูงสุดกี่รูป
- ต้องบีบอัดรูปอัตโนมัติไหม
- ขนาดไฟล์สูงสุดต่อรูป เช่น 5MB หรือ 10MB

Definition of Done:

- AS upload รูปจากมือถือได้
- Admin เปิดดูรูปได้
- ระบบ reject ไฟล์ที่ไม่ใช่รูปหรือใหญ่เกินกำหนด

---

## Phase 4 — Reporting / Export for Admin

เป้าหมาย: Admin เอาข้อมูลไปใช้งานต่อได้จริง

งานหลัก:

1. Export survey progress เป็น Excel/CSV
2. Export submitted responses เป็น Excel/CSV
3. Include branch/account/region/AS/status/deadline/submitted_at
4. Include answer columns by question
5. Include photo links/file paths
6. เพิ่ม filter by survey, account, region, AS, status
7. เพิ่ม pending branch list
8. เพิ่ม overdue report

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- Report format ต้อง Account-first เหมือน feedback report ไหม
- ต้องแยก CAT/Region ใน export หรือเฉพาะ dashboard
- ต้อง export เป็น Excel จริง `.xlsx` หรือ CSV เพียงพอ

Definition of Done:

- Admin กด export แล้วได้ไฟล์ใช้งานต่อได้
- เห็น pending/overdue ชัดเจน
- ข้อมูลรูปไม่หาย

---

## Phase 5 — Authentication / User Management Hardening

เป้าหมาย: ระบบปลอดภัยพอสำหรับทีมจริง

งานหลัก:

1. เปลี่ยน Admin seed PIN
2. เพิ่มหน้า Admin จัดการ AS users
3. เปลี่ยน PIN / reset PIN
4. เพิ่ม session expiration
5. เปลี่ยน in-memory token เป็น signed token หรือ DB sessions
6. เพิ่ม role permission check ทุก endpoint
7. เพิ่ม audit log สำหรับ login/import/submit/publish
8. ปิด CORS แบบเปิดกว้างเมื่อ deploy จริง

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- AS เปลี่ยน PIN เองได้ไหม หรือ Admin reset เท่านั้น
- ต้องมี user role ระดับ Area/Region manager ไหม
- session หมดอายุในกี่ชั่วโมง

Definition of Done:

- ไม่มี Admin PIN test
- restart server แล้ว session logic ยังควบคุมได้
- Admin จัดการ user ได้
- audit log ตรวจย้อนหลังได้

---

## Phase 6 — Data Safety / Backup / Recovery

เป้าหมาย: ข้อมูลไม่หายเมื่อ VPS restart หรือระบบพัง

งานหลัก:

1. ระบุ data ที่ต้อง backup: SQLite DB + uploads + config
2. สร้าง backup script
3. ตั้ง backup schedule
4. ทดสอบ restore DB
5. ทดสอบ restore uploaded photos
6. เขียน runbook กู้ระบบ
7. เก็บ backup นอก folder web root

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- ต้อง backup ถี่แค่ไหน: รายวัน/ทุก 6 ชม./ทุกชั่วโมง
- ต้องเก็บ backup กี่วัน
- ต้องส่ง backup ไป Google Drive หรือเก็บใน VPS ก่อน

Definition of Done:

- มี backup file ที่สร้างอัตโนมัติ
- restore test ผ่านอย่างน้อย 1 ครั้ง
- มี runbook สำหรับกู้ระบบ

---

## Phase 7 — Deployment for Real Users

เป้าหมาย: เปิดให้ user เข้าใช้งานจริงแบบควบคุมความเสี่ยง

งานหลัก:

1. เลือก exposure method: SSH tunnel, VPN, Cloudflare Tunnel, reverse proxy + domain
2. เปิด HTTPS หรือ tunnel ที่ปลอดภัย
3. ตั้ง backend process ให้ restart อัตโนมัติ
4. ตั้ง frontend/static hosting
5. ตั้ง environment config แยก dev/prod
6. เพิ่ม health check
7. จำกัด public access เฉพาะที่จำเป็น
8. ทดสอบจากมือถือ/PC ของ user จริง

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- ต้องการให้ AS เข้าผ่าน public link จากมือถือไหม
- มี domain อยู่แล้วไหม
- รับความเสี่ยง Cloudflare Tunnel ได้ไหม หรืออยาก VPN/private ก่อน

Definition of Done:

- User เปิด URL ได้จากมือถือ/PC
- Server restart แล้วกลับมาเอง
- API health check ผ่าน
- ไม่มี port dev เปิดโล่งโดยไม่ตั้งใจ

---

## Phase 8 — Pilot Test with Small AS Group

เป้าหมาย: ทดสอบกับคนจริงกลุ่มเล็กก่อน rollout

งานหลัก:

1. เลือก AS 2-5 คนสำหรับ pilot
2. สร้าง survey test แบบงานจริง
3. ให้ AS login/รับงาน/ส่งรูป/ส่งคำตอบ
4. Admin ดู progress/export
5. เก็บ feedback ปัญหาการใช้งาน
6. แก้ bug/UX ที่เจอ
7. ทำ quick guide ภาษาไทยสำหรับ AS

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- กลุ่ม pilot คือใคร
- จะใช้ข้อมูลจริงหรือ survey dummy
- ต้องการคู่มือแบบภาพหน้าจอไหม

Definition of Done:

- AS pilot ส่งงานสำเร็จ
- Admin export แล้วใช้ต่อได้
- ปัญหา critical ถูกแก้ก่อน rollout

---

## Phase 9 — Rollout / Training / Operations

เป้าหมาย: ใช้งานจริงเป็น routine ได้

งานหลัก:

1. สรุปคู่มือ AS
2. สรุปคู่มือ Admin
3. ตั้ง support path: ถ้า AS login ไม่ได้/ส่งรูปไม่ได้ ต้องแจ้งใคร
4. ตั้ง operating schedule เช่น check overdue ทุกวัน
5. ทำ dashboard/report routine
6. สรุป known issues และ workaround
7. เพิ่ม monitoring/alert เบื้องต้น

สิ่งที่ Armz ต้องช่วยตัดสินใจ:

- ช่องทาง support สำหรับ AS
- ใครเป็น Admin ตัวจริง
- rollout ทีละ account/region หรือเปิดทั้งหมด

Definition of Done:

- User ใช้งานจริงได้โดยไม่ต้องให้ Genos เฝ้าทุกขั้น
- Admin มีคู่มือและ routine
- มี backup + monitoring + support process

---

## Recommended Build Order

Genos แนะนำลำดับนี้:

1. Phase 1: ต่อ Prototype UI กับ Backend API
2. Phase 3 แบบย่อ: ทำ photo upload จริง
3. Phase 4: Export report
4. Phase 5: Auth hardening
5. Phase 2: Admin create survey ผ่านเว็บ
6. Phase 6: Backup/recovery
7. Phase 7: Deploy real access
8. Phase 8: Pilot
9. Phase 9: Rollout

เหตุผล: ถ้าต่อ UI + upload + export ได้ก่อน จะทดสอบ workflow จริงได้เร็วที่สุด ส่วน Admin create survey ผ่านเว็บทำทีหลังได้ เพราะช่วงแรกยังใช้ Excel import ช่วยได้

## Immediate Next Step

เริ่ม Phase 1 โดยต่อ prototype กับ API จริงก่อน

ไฟล์หลักที่จะต้องแก้:

- `/opt/data/as-survey-system/prototype/index.html`

Backend ที่ใช้:

- `/opt/data/as-survey-system/backend`

Verification:

- เปิด backend port 8030
- เปิด prototype
- AS login ผ่าน UI
- AS เห็น tasks จาก DB
- AS submit แล้ว Admin progress เปลี่ยน

## Approval Gates

ต้องถาม Armz ก่อนทำสิ่งเหล่านี้:

- เปิด public URL ให้ user จริง
- ใช้ paid API หรือ paid cloud service
- เปลี่ยน domain/DNS/reverse proxy
- ลบข้อมูลจริง
- ส่งข้อมูลจริงออกนอก VPS
- เปิด access ให้คนนอก pilot
