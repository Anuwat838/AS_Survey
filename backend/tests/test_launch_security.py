import os
import time

from fastapi.testclient import TestClient

from app import db
from app.main import create_app
from app.security import verify_pin
from tests.test_backend_mvp import FIXED_XLSX, auth_header
from app.importer import import_workbook


def make_security_client(tmp_path, session_ttl_seconds=None, allowed_origins=None):
    db_path = tmp_path / 'security.db'
    db.init_db(db_path)
    import_workbook(FIXED_XLSX, db_path=db_path)
    kwargs = {}
    if session_ttl_seconds is not None:
        kwargs['session_ttl_seconds'] = session_ttl_seconds
    if allowed_origins is not None:
        kwargs['allowed_origins'] = allowed_origins
    return TestClient(create_app(db_path=db_path, **kwargs)), db_path


def test_admin_security_status_warns_when_seed_pin_is_unchanged(tmp_path):
    client, _ = make_security_client(tmp_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    res = client.get('/api/admin/security/status', headers=headers)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['admin_default_pin'] is True
    assert payload['launch_locked'] is True
    assert any('Admin PIN' in warning for warning in payload['warnings'])


def test_admin_can_change_own_pin_and_default_pin_warning_clears(tmp_path):
    client, db_path = make_security_client(tmp_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    res = client.post('/api/auth/change-pin', headers=headers, json={'current_pin': '0000', 'new_pin': '246810'})
    assert res.status_code == 200, res.text
    assert res.json()['ok'] is True

    old_login = client.post('/api/auth/admin-login', json={'login_code': 'ADM01', 'pin': '0000'})
    assert old_login.status_code == 401
    new_headers = auth_header(client, 'ADM01', '246810', admin=True)
    status = client.get('/api/admin/security/status', headers=new_headers)
    assert status.status_code == 200
    assert status.json()['admin_default_pin'] is False
    assert status.json()['launch_locked'] is False
    pin_hash = db.connect(db_path).execute("SELECT pin_hash FROM users WHERE login_code='ADM01'").fetchone()['pin_hash']
    assert verify_pin('246810', pin_hash)


def test_change_pin_rejects_wrong_current_pin_and_weak_pin(tmp_path):
    client, _ = make_security_client(tmp_path)
    headers = auth_header(client, 'ADM01', '0000', admin=True)
    wrong = client.post('/api/auth/change-pin', headers=headers, json={'current_pin': '9999', 'new_pin': '246810'})
    assert wrong.status_code == 400
    weak = client.post('/api/auth/change-pin', headers=headers, json={'current_pin': '0000', 'new_pin': '123'})
    assert weak.status_code == 400


def test_session_expires_after_configured_ttl(tmp_path):
    client, _ = make_security_client(tmp_path, session_ttl_seconds=1)
    headers = auth_header(client, 'BKK10', '800250')
    immediate = client.get('/api/as/tasks', headers=headers)
    assert immediate.status_code == 200
    time.sleep(1.2)
    expired = client.get('/api/as/tasks', headers=headers)
    assert expired.status_code == 401
    assert expired.json()['detail'] == 'Session expired'


def test_cors_allowed_origins_are_not_wildcard_for_pilot(tmp_path):
    client, _ = make_security_client(tmp_path, allowed_origins=['http://localhost:8021'])
    ok = client.options('/health', headers={
        'Origin': 'http://localhost:8021',
        'Access-Control-Request-Method': 'GET',
    })
    assert ok.status_code == 200
    assert ok.headers['access-control-allow-origin'] == 'http://localhost:8021'
    blocked = client.options('/health', headers={
        'Origin': 'http://evil.example',
        'Access-Control-Request-Method': 'GET',
    })
    assert 'access-control-allow-origin' not in blocked.headers
