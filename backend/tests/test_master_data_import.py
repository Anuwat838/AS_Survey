from pathlib import Path

from app import db
from app.importer import import_workbook
from app.security import hash_pin, verify_pin
from tests.test_backend_mvp import FIXED_XLSX

V2_WORKBOOK = Path('/opt/data/cache/documents/doc_8a457841529d_as_survey_system_fixed V.2.xlsx')
MASTER_WORKBOOK = FIXED_XLSX


def test_master_data_import_updates_as_and_branches_without_touching_surveys_or_admin_pin(tmp_path):
    from app.importer import import_master_data_workbook

    db_path = tmp_path / 'pilot.db'
    db.init_db(db_path)
    import_workbook(FIXED_XLSX, db_path=db_path)

    conn = db.connect(db_path)
    conn.execute("UPDATE users SET pin_hash=? WHERE login_code='ADM01' AND role='super_admin'", (hash_pin('246810'),))
    conn.commit()
    before = {
        'surveys': conn.execute('SELECT COUNT(*) FROM surveys').fetchone()[0],
        'tasks': conn.execute('SELECT COUNT(*) FROM survey_tasks').fetchone()[0],
        'questions': conn.execute('SELECT COUNT(*) FROM survey_questions').fetchone()[0],
        'responses': conn.execute('SELECT COUNT(*) FROM survey_responses').fetchone()[0],
        'response_files': conn.execute('SELECT COUNT(*) FROM response_files').fetchone()[0],
    }
    assert before['surveys'] > 0
    assert before['tasks'] > 0

    result = import_master_data_workbook(MASTER_WORKBOOK, db_path=db_path, backup_before_import=False)

    assert result['valid'] is True
    assert result['mode'] == 'master_data'
    assert result['imported']['as_users'] == 2
    assert result['imported']['branches'] == 16

    conn = db.connect(db_path)
    after = {
        'surveys': conn.execute('SELECT COUNT(*) FROM surveys').fetchone()[0],
        'tasks': conn.execute('SELECT COUNT(*) FROM survey_tasks').fetchone()[0],
        'questions': conn.execute('SELECT COUNT(*) FROM survey_questions').fetchone()[0],
        'responses': conn.execute('SELECT COUNT(*) FROM survey_responses').fetchone()[0],
        'response_files': conn.execute('SELECT COUNT(*) FROM response_files').fetchone()[0],
    }
    assert after == before
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role='as'").fetchone()[0] == 2
    assert conn.execute('SELECT COUNT(*) FROM branches').fetchone()[0] == 16
    admin = conn.execute("SELECT pin_hash FROM users WHERE login_code='ADM01' AND role='super_admin'").fetchone()
    assert admin is not None
    assert verify_pin('246810', admin['pin_hash'])
    assert not verify_pin('0000', admin['pin_hash'])


def test_master_data_dry_run_does_not_write_database(tmp_path):
    from app.importer import import_master_data_workbook

    db_path = tmp_path / 'pilot.db'
    db.init_db(db_path)
    import_workbook(FIXED_XLSX, db_path=db_path)
    conn = db.connect(db_path)
    before_as = conn.execute("SELECT COUNT(*) FROM users WHERE role='as'").fetchone()[0]
    before_branches = conn.execute('SELECT COUNT(*) FROM branches').fetchone()[0]

    result = import_master_data_workbook(MASTER_WORKBOOK, db_path=db_path, dry_run=True)

    assert result['valid'] is True
    assert result['dry_run'] is True
    assert result['summary']['as_user_count'] == 2
    assert result['summary']['branch_count'] == 16
    conn = db.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role='as'").fetchone()[0] == before_as
    assert conn.execute('SELECT COUNT(*) FROM branches').fetchone()[0] == before_branches
