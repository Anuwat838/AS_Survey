from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from .deps import get_db_path, require_admin
from .importer import import_upload_bytes

router = APIRouter(prefix="/api/admin/import", tags=["import"])


@router.post("/excel")
async def import_excel(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only; do not write to DB"),
    user: dict = Depends(require_admin),
    db_path=Depends(get_db_path),
):
    content = await file.read()
    return import_upload_bytes(
        content,
        file.filename or "upload.xlsx",
        db_path=db_path,
        dry_run=dry_run,
        backup_before_import=not dry_run,
    )
