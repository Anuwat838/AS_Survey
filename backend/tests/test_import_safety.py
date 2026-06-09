from pathlib import Path

from fastapi.testclient import TestClient

from app import db
from app.importer import read_xlsx, validate_workbook
from app.main import create_app
from tests.test_backend_mvp import FIXED_XLSX, auth_header, make_client


def test_pilot_workbook_validation_reports_missing_pins_and_orphan_tasks():
    data = read_xlsx(FIXED_XLSX)
    data['AS_USERS'][0]['pin'] = ''
    data['SURVEY_BRANCHES'][0]['assigned_as_code'] = 'NO_SUCH_AS'
    result = validate_workbook(data)
    assert result['valid'] is False
    assert any('AS_USERS' in e and 'missing pin' in e for e in result['errors'])
    assert any('SURVEY_BRANCHES' in e and 'AS missing NO_SUCH_AS' in e for e in result['errors'])
    assert result['summary']['error_count'] >= 2
    assert result['summary']['as_user_count'] == 2
    assert result['summary']['branch_count'] == 16


def test_admin_import_dry_run_validates_without_writing_database(tmp_path):
    client, db_path = make_client(tmp_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    before = db.connect(db_path).execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    with FIXED_XLSX.open('rb') as f:
        res = client.post(
            '/api/admin/import/excel?dry_run=true',
            headers=headers,
            files={'file': ('fixed.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['dry_run'] is True
    assert payload['valid'] is True
    assert 'backup_dir' not in payload
    after = db.connect(db_path).execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    assert after == before


def test_admin_import_creates_backup_before_writing(tmp_path):
    db_path = tmp_path / 'test.db'
    db.init_db(db_path)
    app = create_app(db_path=db_path)
    client = TestClient(app)
    # Seed only admin so the route can authenticate, then import the workbook.
    import_workbook = __import__('app.importer', fromlist=['import_workbook']).import_workbook
    import_workbook(FIXED_XLSX, db_path=db_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    with FIXED_XLSX.open('rb') as f:
        res = client.post(
            '/api/admin/import/excel',
            headers=headers,
            files={'file': ('fixed.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['valid'] is True
    backup_dir = Path(payload['backup_dir'])
    assert backup_dir.exists()
    assert (backup_dir / 'as_survey.db').exists()
    assert (backup_dir / 'manifest.json').exists()


def test_validate_workbook_rejects_excel_error_tokens_in_master_data():
    data = {
        'AS_USERS': [{'as_code': 'AS01', 'as_name': 'A', 'region': 'BANGOK', 'phone': '', 'email': '', 'pin': '123456', 'status': 'active', 'role': 'AS'}],
        'BRANCHES': [{'branch_code': 'B01', 'branch_name': 'Branch', 'account': 'ACC', 'region': '#VALUE!', 'province': 'P', 'assigned_as_code': 'AS01', 'status': 'active', 'note': ''}],
        'SURVEYS': [], 'SURVEY_BRANCHES': [], 'QUESTIONS': [], 'RESPONSES': [], 'RESPONSE_FILES': [], 'STATUS_LOG': [], 'ADMIN_SETTINGS': [],
    }

    result = validate_workbook(data)

    assert result['valid'] is False
    assert any('Excel error token' in error for error in result['errors'])
