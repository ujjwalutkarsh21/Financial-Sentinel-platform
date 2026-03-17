"""File upload service — saves to backend/tmp/uploads/ and tracks IDs."""

import os
import uuid

from fastapi import UploadFile
from schemas.chat_schema import UploadResponse

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory mapping: fileId → {path, name}
_file_registry: dict[str, dict] = {}


async def save_file(file: UploadFile) -> UploadResponse:
    """Save an uploaded file and return its metadata."""
    file_id = str(uuid.uuid4())
    filename = file.filename or f"{file_id}.bin"
    dest = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")

    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)

    _file_registry[file_id] = {"path": dest, "name": filename}

    return UploadResponse(
        fileId=file_id,
        url=f"/tmp/uploads/{file_id}_{filename}",
        name=filename,
    )


def get_file_path(file_id: str) -> str | None:
    """Look up a file path by its ID."""
    entry = _file_registry.get(file_id)
    return entry["path"] if entry else None
