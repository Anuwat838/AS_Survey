from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.importer import import_workbook, read_xlsx, validate_workbook
from app.main import create_app
from app.security import hash_pin, verify_pin

FIXED_XLSX = Path('/opt/data/cache/documents/as_survey_system_fixed.xlsx')
EXPECTED_COUNTS = {
    'AS_USERS': 2,
    'BRANCHES': 16,
    'SURVEYS': 4,
    'SURVEY_BRANCHES': 6,
    'QUESTIONS': 5,
    'RESPONSES': 5,
    'RESPONSE_FILES': 4,
    'STATUS_LOG': 4,
    'ADMIN_SETTINGS': 9,
}


def make_client(tmp_path):
    db_path = tmp_path / 'test.db'
    db.init_db(db_path)
    import_workbook(FIXED_XLSX, db_path=db_path)
    app = create_app(db_path=db_path)
    return TestClient(app), db_path


def auth_header(client, code='BKK10', pin='800250', admin=False):
    endpoint = '/api/auth/admin-login' if admin else '/api/auth/as-login'
    res = client.post(endpoint, json={'login_code': code, 'pin': pin})
    assert res.status_code == 200, res.text
    token = res.json()['token']
    return {'Authorization': f'Bearer {token}'}


def test_schema_initializes_core_tables(tmp_path):
    conn = db.init_db(tmp_path / 'schema.db')
    tables = {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    for name in ['users', 'branches', 'surveys', 'survey_tasks', 'survey_questions', 'survey_progress', 'survey_progress_by_as']:
        assert name in tables


def test_pin_hashing_verifies_correct_pin_and_rejects_wrong_pin():
    stored = hash_pin('800250')
    assert stored != '800250'
    assert verify_pin('800250', stored)
    assert not verify_pin('9999', stored)


def test_xlsx_reader_reads_expected_sheet_counts():
    data = read_xlsx(FIXED_XLSX)
    counts = {k: len(v) for k, v in data.items()}
    for sheet, count in EXPECTED_COUNTS.items():
        assert counts[sheet] == count


def test_workbook_validation_accepts_fixed_workbook():
    result = validate_workbook(read_xlsx(FIXED_XLSX))
    assert result['valid'] is True
    assert result['errors'] == []
    assert result['counts']['BRANCHES'] == 16


def test_import_workbook_loads_database_and_hashes_pins(tmp_path):
    db_path = tmp_path / 'import.db'
    db.init_db(db_path)
    result = import_workbook(FIXED_XLSX, db_path=db_path)
    assert result['valid'] is True
    conn = db.connect(db_path)
    assert conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c'] == 3
    assert conn.execute('SELECT COUNT(*) c FROM branches').fetchone()['c'] == 16
    assert conn.execute('SELECT COUNT(*) c FROM survey_tasks').fetchone()['c'] == 6
    pin_hash = conn.execute("SELECT pin_hash FROM users WHERE login_code='BKK10'").fetchone()['pin_hash']
    assert pin_hash.startswith('pbkdf2_sha256$')
    assert verify_pin('800250', pin_hash)


def test_auth_routes_login_and_reject_wrong_pin(tmp_path):
    client, _ = make_client(tmp_path)
    ok = client.post('/api/auth/as-login', json={'login_code': 'BKK10', 'pin': '800250'})
    assert ok.status_code == 200
    assert ok.json()['user']['role'] == 'as'
    bad = client.post('/api/auth/as-login', json={'login_code': 'BKK10', 'pin': '9999'})
    assert bad.status_code == 401
    adm = client.post('/api/auth/admin-login', json={'login_code': 'ADM01', 'pin': '0000'})
    assert adm.status_code == 200


def test_as_tasks_are_grouped_by_survey_and_only_own_tasks(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_header(client, 'BKK10', '800250')
    res = client.get('/api/as/tasks', headers=headers)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert 'active_surveys' in payload and 'completed_surveys' in payload
    all_tasks = [t for s in payload['active_surveys'] + payload['completed_surveys'] for t in s['tasks']]
    assert all_tasks
    assert {t['assigned_as_code'] for t in all_tasks} == {'BKK10'}
    assert all('deadline' in t for t in all_tasks)


def test_as_can_submit_owned_task_and_completed_remains_visible(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_header(client, 'BKK10', '800250')
    tasks = client.get('/api/as/tasks', headers=headers).json()
    task = next(t for s in tasks['active_surveys'] for t in s['tasks'] if t['status'] != 'submitted')
    detail = client.get(f"/api/as/tasks/{task['id']}", headers=headers)
    assert detail.status_code == 200
    answers = []
    for q in detail.json()['questions']:
        value = '1' if q['answer_type'] == 'number' else 'ok'
        item = {'question_id': q['id'], 'answer': value}
        if q.get('photo_required'):
            item['files'] = [{'file_name': 'photo.jpg', 'file_url': 'https://example.com/photo.jpg'}]
        answers.append(item)
    submit = client.post(f"/api/as/tasks/{task['id']}/submit", headers=headers, json={'answers': answers})
    assert submit.status_code == 200, submit.text
    after = client.get('/api/as/tasks', headers=headers).json()
    all_tasks = [t for s in after['active_surveys'] + after['completed_surveys'] for t in s['tasks']]
    submitted = [t for t in all_tasks if t['id'] == task['id']][0]
    assert submitted['status'] == 'submitted'


def test_as_can_upload_real_photos_for_question_with_limits(tmp_path):
    client, db_path = make_client(tmp_path)
    headers = auth_header(client, 'BKK10', '800250')
    tasks = client.get('/api/as/tasks', headers=headers).json()
    chosen = None
    for survey in tasks['active_surveys']:
        for candidate in survey['tasks']:
            if candidate['status'] == 'submitted':
                continue
            detail_payload = client.get(f"/api/as/tasks/{candidate['id']}", headers=headers).json()
            photo_question = next((q for q in detail_payload['questions'] if q.get('allow_photo') or q.get('photo_required')), None)
            if photo_question:
                chosen = (candidate, detail_payload, photo_question)
                break
        if chosen:
            break
    task, detail, question = chosen

    files = [
        ('files', ('price-1.jpg', b'fake image 1', 'image/jpeg')),
        ('files', ('price-2.png', b'fake image 2', 'image/png')),
    ]
    uploaded = client.post(
        f"/api/as/tasks/{task['id']}/questions/{question['id']}/files",
        headers=headers,
        files=files,
    )
    assert uploaded.status_code == 200, uploaded.text
    data = uploaded.json()
    assert data['count'] == 2
    assert all(item['file_url'].startswith('/uploads/') for item in data['files'])
    assert all(item['file_path'] for item in data['files'])
    for item in data['files']:
        assert Path(item['file_path']).exists()

    too_many = client.post(
        f"/api/as/tasks/{task['id']}/questions/{question['id']}/files",
        headers=headers,
        files=[('files', (f'p{i}.jpg', b'x', 'image/jpeg')) for i in range(6)],
    )
    assert too_many.status_code == 400

    bad_type = client.post(
        f"/api/as/tasks/{task['id']}/questions/{question['id']}/files",
        headers=headers,
        files=[('files', ('note.txt', b'not an image', 'text/plain'))],
    )
    assert bad_type.status_code == 400


def _find_open_photo_task(client, headers):
    tasks = client.get('/api/as/tasks', headers=headers).json()
    for survey in tasks['active_surveys']:
        for candidate in survey['tasks']:
            if candidate['status'] == 'submitted':
                continue
            detail_payload = client.get(f"/api/as/tasks/{candidate['id']}", headers=headers).json()
            photo_question = next((q for q in detail_payload['questions'] if q.get('allow_photo') or q.get('photo_required')), None)
            if photo_question:
                return candidate, detail_payload, photo_question
    raise AssertionError('No open photo task found')


def test_as_and_admin_can_review_submitted_answers_with_files(tmp_path):
    client, _ = make_client(tmp_path)
    as_headers = auth_header(client, 'BKK10', '800250')
    task, detail, photo_question = _find_open_photo_task(client, as_headers)
    upload = client.post(
        f"/api/as/tasks/{task['id']}/questions/{photo_question['id']}/files",
        headers=as_headers,
        files=[('files', ('review.jpg', b'img', 'image/jpeg'))],
    )
    assert upload.status_code == 200, upload.text
    uploaded_files = upload.json()['files']

    answers = []
    for q in detail['questions']:
        value = '1' if q['answer_type'] == 'number' else 'ok'
        item = {'question_id': q['id'], 'answer': value}
        if q['id'] == photo_question['id']:
            item['files'] = uploaded_files
        elif q.get('photo_required'):
            item['files'] = [{'file_name': 'required.jpg', 'file_url': '/uploads/required.jpg', 'file_path': str(tmp_path / 'required.jpg'), 'file_type': 'image/jpeg'}]
        answers.append(item)
    submitted = client.post(f"/api/as/tasks/{task['id']}/submit", headers=as_headers, json={'answers': answers})
    assert submitted.status_code == 200, submitted.text

    as_detail = client.get(f"/api/as/tasks/{task['id']}", headers=as_headers)
    assert as_detail.status_code == 200
    latest = as_detail.json()['latest_response']
    assert latest['response_id'] == submitted.json()['response_id']
    photo_answer = next(a for a in latest['answers'] if a['question_id'] == photo_question['id'])
    assert photo_answer['files'][0]['file_name'] == 'review.jpg'
    assert photo_answer['files'][0]['file_url'].startswith('/uploads/')

    admin_headers = auth_header(client, 'ADM01', '0000', admin=True)
    admin_res = client.get(f"/api/admin/surveys/{detail['survey_id']}/responses", headers=admin_headers)
    assert admin_res.status_code == 200, admin_res.text
    response = next(r for r in admin_res.json()['responses'] if r['task_id'] == task['id'])
    assert response['branch_name'] == task['branch_name']
    admin_photo_answer = next(a for a in response['answers'] if a['question_id'] == photo_question['id'])
    assert admin_photo_answer['files'][0]['file_name'] == 'review.jpg'
    assert admin_photo_answer['files'][0]['file_url'].startswith('/uploads/')


def test_admin_response_status_is_compact_and_hides_answers_and_file_urls(tmp_path):
    client, _ = make_client(tmp_path)
    as_headers = auth_header(client, 'BKK10', '800250')
    task, detail, photo_question = _find_open_photo_task(client, as_headers)
    upload = client.post(
        f"/api/as/tasks/{task['id']}/questions/{photo_question['id']}/files",
        headers=as_headers,
        files=[('files', ('status.jpg', b'img', 'image/jpeg'))],
    )
    assert upload.status_code == 200
    answers = []
    for q in detail['questions']:
        item = {'question_id': q['id'], 'answer': '1' if q['answer_type'] == 'number' else 'not for admin display'}
        if q['id'] == photo_question['id'] or q.get('photo_required'):
            item['files'] = upload.json()['files']
        answers.append(item)
    submitted = client.post(f"/api/as/tasks/{task['id']}/submit", headers=as_headers, json={'answers': answers})
    assert submitted.status_code == 200

    admin_headers = auth_header(client, 'ADM01', '0000', admin=True)
    res = client.get(f"/api/admin/surveys/{detail['survey_id']}/response-status", headers=admin_headers)
    assert res.status_code == 200, res.text
    payload_text = res.text
    assert 'not for admin display' not in payload_text
    assert 'file_url' not in payload_text
    assert 'files' not in payload_text
    row = next(r for r in res.json()['responses'] if r['task_id'] == task['id'])
    assert row['answer_status'] == 'complete'
    assert row['photo_status'] == 'attached'
    assert row['answered_count'] == row['question_count']
    assert row['photo_attached_count'] >= 1


def test_admin_progress_and_import_route(tmp_path):
    client, _ = make_client(tmp_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    res = client.get('/api/admin/surveys/progress', headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()['surveys']
    assert len(rows) == 4
    assert all('completion_pct' in r for r in rows)
    first_id = rows[0]['survey_id']
    detail = client.get(f'/api/admin/surveys/{first_id}/progress', headers=headers)
    assert detail.status_code == 200
    with FIXED_XLSX.open('rb') as f:
        imp = client.post('/api/admin/import/excel', headers=headers, files={'file': ('fixed.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert imp.status_code == 200, imp.text
    assert imp.json()['valid'] is True


def test_admin_can_create_select_questions_and_publish_survey_from_web_flow(tmp_path):
    db_path = tmp_path / 'create-survey.db'
    conn = db.init_db(db_path)
    with conn:
        conn.execute("INSERT INTO users(login_code,name,pin_hash,role,status) VALUES(?,?,?,?,?)", ('ADM01', 'Admin', hash_pin('0000'), 'super_admin', 'active'))
        cur = conn.execute("INSERT INTO users(login_code,name,region,pin_hash,role,status) VALUES(?,?,?,?,?,?)", ('BKK10', 'AS Bangkok', 'BANGKOK', hash_pin('800250'), 'as', 'active'))
        as_id = cur.lastrowid
        conn.execute("INSERT INTO branches(branch_code,branch_name,account,region,province,assigned_user_id,status) VALUES(?,?,?,?,?,?,?)", ('BC001', 'BIG C Ekkamai', 'BIG C', 'BANGKOK', 'BANGKOK', as_id, 'active'))
    client = TestClient(create_app(db_path=db_path))
    headers = auth_header(client, 'ADM01', '0000', admin=True)

    filters = client.get('/api/admin/filters', headers=headers)
    assert filters.status_code == 200, filters.text
    assert filters.json()['accounts']

    branches = client.get('/api/admin/branches?account=BIG C&region=BANGKOK', headers=headers)
    assert branches.status_code == 200, branches.text
    items = branches.json()['items']
    assert items
    selected_codes = [items[0]['branch_code']]

    created = client.post(
        '/api/admin/surveys',
        headers=headers,
        json={'title': 'Web Create Survey', 'category': 'AC', 'description': 'created from admin page', 'deadline': '2026-06-30'},
    )
    assert created.status_code == 200, created.text
    survey = created.json()
    assert survey['status'] == 'draft'
    assert survey['survey_code'].startswith('SVY-')

    basket = client.post(f"/api/admin/surveys/{survey['survey_id']}/selected-branches", headers=headers, json={'branch_codes': selected_codes})
    assert basket.status_code == 200, basket.text
    assert basket.json()['added'] == 1
    assert basket.json()['total_selected'] == 1

    question = client.post(
        f"/api/admin/surveys/{survey['survey_id']}/questions",
        headers=headers,
        json={'question_order': 1, 'question_text': 'ราคา competitor', 'answer_type': 'number', 'required': True, 'allow_photo': True, 'photo_required': True, 'options': [], 'help_text': 'แนบรูปป้ายราคา'},
    )
    assert question.status_code == 200, question.text
    assert question.json()['question_code'] == 'Q1'

    published = client.post(f"/api/admin/surveys/{survey['survey_id']}/publish", headers=headers)
    assert published.status_code == 200, published.text
    assert published.json()['created_tasks'] == 1
    assert published.json()['status'] == 'published'

    conn = db.connect(db_path)
    row = conn.execute("SELECT status FROM surveys WHERE id=?", (survey['survey_id'],)).fetchone()
    assert row['status'] == 'published'
    task_count = conn.execute("SELECT COUNT(*) c FROM survey_tasks WHERE survey_id=?", (survey['survey_id'],)).fetchone()['c']
    assert task_count == 1


def test_admin_can_manage_users_and_reset_pin(tmp_path):
    db_path = tmp_path / 'admin-users.db'
    conn = db.init_db(db_path)
    with conn:
        conn.execute("INSERT INTO users(login_code,name,pin_hash,role,status) VALUES(?,?,?,?,?)", ('ADM01', 'Admin', hash_pin('0000'), 'super_admin', 'active'))
    client = TestClient(create_app(db_path=db_path))
    headers = auth_header(client, 'ADM01', '0000', admin=True)

    created = client.post('/api/admin/users', headers=headers, json={
        'login_code': 'AS999',
        'name': 'AS Test',
        'region': 'BANGKOK',
        'phone': '0800000000',
        'email': 'as@example.com',
        'role': 'as',
        'status': 'active',
        'pin': '123456',
    })
    assert created.status_code == 200, created.text
    user_id = created.json()['user']['id']
    assert created.json()['user']['login_code'] == 'AS999'
    assert 'pin_hash' not in created.json()['user']

    login = client.post('/api/auth/as-login', json={'login_code': 'AS999', 'pin': '123456'})
    assert login.status_code == 200, login.text

    updated = client.patch(f'/api/admin/users/{user_id}', headers=headers, json={'name': 'AS Updated', 'status': 'inactive'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['user']['name'] == 'AS Updated'
    blocked = client.post('/api/auth/as-login', json={'login_code': 'AS999', 'pin': '123456'})
    assert blocked.status_code == 401

    reactivate = client.patch(f'/api/admin/users/{user_id}', headers=headers, json={'status': 'active'})
    assert reactivate.status_code == 200, reactivate.text
    reset = client.post(f'/api/admin/users/{user_id}/pin', headers=headers, json={'new_pin': '654321'})
    assert reset.status_code == 200, reset.text
    assert client.post('/api/auth/as-login', json={'login_code': 'AS999', 'pin': '123456'}).status_code == 401
    assert client.post('/api/auth/as-login', json={'login_code': 'AS999', 'pin': '654321'}).status_code == 200

    users = client.get('/api/admin/users?role=as&q=Updated', headers=headers)
    assert users.status_code == 200, users.text
    assert users.json()['items'][0]['login_code'] == 'AS999'
    assert 'pin_hash' not in users.json()['items'][0]


def test_admin_can_upload_branch_list_csv_and_upsert_branches(tmp_path):
    db_path = tmp_path / 'branches-upload.db'
    conn = db.init_db(db_path)
    with conn:
        conn.execute("INSERT INTO users(login_code,name,pin_hash,role,status) VALUES(?,?,?,?,?)", ('ADM01', 'Admin', hash_pin('0000'), 'super_admin', 'active'))
        cur = conn.execute("INSERT INTO users(login_code,name,region,pin_hash,role,status) VALUES(?,?,?,?,?,?)", ('BKK10', 'AS Bangkok', 'BANGKOK', hash_pin('800250'), 'as', 'active'))
        as_id = cur.lastrowid
        conn.execute("INSERT INTO branches(branch_code,branch_name,account,region,province,assigned_user_id,status) VALUES(?,?,?,?,?,?,?)", ('BC001', 'Old Name', 'OLD', 'BANGKOK', 'BANGKOK', as_id, 'active'))
    client = TestClient(create_app(db_path=db_path))
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    csv_text = 'branch_code,branch_name,account,region,province,assigned_as_code,status,note\nBC001,New Name,BIG C,BANGKOK,BANGKOK,BKK10,active,updated\nBC002,Lotus Rama,LOTUS,CENTRAL,PATHUM,BKK10,active,new row\n'

    dry = client.post('/api/admin/branches/import-csv?dry_run=true', headers=headers, files={'file': ('branches.csv', csv_text, 'text/csv')})
    assert dry.status_code == 200, dry.text
    assert dry.json()['dry_run'] is True
    assert dry.json()['valid'] is True
    assert dry.json()['summary']['rows'] == 2
    assert db.connect(db_path).execute("SELECT branch_name FROM branches WHERE branch_code='BC001'").fetchone()['branch_name'] == 'Old Name'

    imported = client.post('/api/admin/branches/import-csv', headers=headers, files={'file': ('branches.csv', csv_text, 'text/csv')})
    assert imported.status_code == 200, imported.text
    assert imported.json()['summary']['inserted'] == 1
    assert imported.json()['summary']['updated'] == 1
    conn = db.connect(db_path)
    assert conn.execute("SELECT branch_name,account FROM branches WHERE branch_code='BC001'").fetchone()['branch_name'] == 'New Name'
    assert conn.execute("SELECT COUNT(*) c FROM branches WHERE branch_code='BC002'").fetchone()['c'] == 1

    bad_csv = 'branch_code,branch_name,account,region,province,assigned_as_code,status\nBC003,Bad,BIG C,BANGKOK,BANGKOK,NOPE,active\n'
    bad = client.post('/api/admin/branches/import-csv', headers=headers, files={'file': ('branches.csv', bad_csv, 'text/csv')})
    assert bad.status_code == 400
    assert 'assigned AS missing' in bad.text
