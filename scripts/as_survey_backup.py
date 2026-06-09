#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def backup_as_survey(root: Path | str = Path('/opt/data/as-survey-system'), output_dir: Path | str | None = None) -> dict:
    root = Path(root)
    backend = root / 'backend'
    db_path = backend / 'as_survey.db'
    uploads_dir = backend / 'uploads'
    if not db_path.exists():
        raise FileNotFoundError(f'Database not found: {db_path}')
    if output_dir is None:
        output_dir = root / 'backups'
    output_dir = Path(output_dir)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = output_dir / f'as-survey-backup-{stamp}'
    backup_dir.mkdir(parents=True, exist_ok=False)

    # Use SQLite backup API so the copy is consistent even while the app runs.
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_dir / 'as_survey.db')
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    if uploads_dir.exists():
        shutil.copytree(uploads_dir, backup_dir / 'uploads')
    else:
        (backup_dir / 'uploads').mkdir()

    manifest = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'root': str(root),
        'database': str(backup_dir / 'as_survey.db'),
        'uploads': str(backup_dir / 'uploads'),
        'backup_dir': str(backup_dir),
    }
    (backup_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description='Backup AS Survey SQLite database and uploaded photos.')
    parser.add_argument('--root', default='/opt/data/as-survey-system')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()
    result = backup_as_survey(root=Path(args.root), output_dir=Path(args.output_dir) if args.output_dir else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
