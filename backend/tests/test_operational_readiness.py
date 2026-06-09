from pathlib import Path
import importlib.util
import sqlite3

from app import db


def test_sqlite_connections_are_tuned_for_60_user_pilot(tmp_path):
    db_path = tmp_path / 'pilot.db'
    conn = db.init_db(db_path)
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert conn.execute('PRAGMA busy_timeout').fetchone()[0] >= 5000
    assert conn.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'
    assert conn.execute('PRAGMA synchronous').fetchone()[0] in (1, 2)  # NORMAL or FULL

    second = db.connect(db_path)
    second.execute('INSERT INTO users(login_code,name,pin_hash,role) VALUES (?,?,?,?)', ('T1','Test','hash','as'))
    second.commit()
    assert conn.execute("SELECT COUNT(*) FROM users WHERE login_code='T1'").fetchone()[0] == 1


def test_backup_script_copies_database_and_uploads(tmp_path):
    root = tmp_path / 'as-survey-system'
    backend = root / 'backend'
    uploads = backend / 'uploads' / 'task_1' / 'question_1'
    uploads.mkdir(parents=True)
    (uploads / 'photo.jpg').write_bytes(b'photo')
    db_path = backend / 'as_survey.db'
    db.init_db(db_path).close()

    script_path = Path('/opt/data/as-survey-system/scripts/as_survey_backup.py')
    spec = importlib.util.spec_from_file_location('as_survey_backup', script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod.backup_as_survey(root=root, output_dir=tmp_path / 'backups')
    backup_dir = Path(result['backup_dir'])
    assert (backup_dir / 'as_survey.db').exists()
    assert (backup_dir / 'uploads' / 'task_1' / 'question_1' / 'photo.jpg').read_bytes() == b'photo'
    copied = sqlite3.connect(backup_dir / 'as_survey.db')
    assert copied.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
