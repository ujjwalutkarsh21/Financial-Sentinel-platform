"""File upload service — saves to backend/tmp/uploads/ and tracks IDs per session."""

import os
import uuid

from fastapi import UploadFile
from schemas.chat_schema import UploadResponse

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory mapping: session_id → { fileId → {path, name, size} }
_file_registry: dict[str, dict[str, dict]] = {}


async def save_file(file: UploadFile, session_id: str) -> UploadResponse:
    """Save an uploaded file and register it under the given session."""
    file_id = str(uuid.uuid4())
    filename = file.filename or f"{file_id}.bin"
    dest = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")

    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)

    session_files = _file_registry.setdefault(session_id, {})
    session_files[file_id] = {
        "path": dest,
        "name": filename,
        "size": len(contents),
    }

    return UploadResponse(
        fileId=file_id,
        url=f"/tmp/uploads/{file_id}_{filename}",
        name=filename,
    )


def get_file_path(file_id: str, session_id: str) -> str | None:
    """Look up a file path by its ID within a session."""
    session_files = _file_registry.get(session_id, {})
    entry = session_files.get(file_id)
    return entry["path"] if entry else None


def get_session_files(session_id: str) -> list[dict]:
    """Return all uploaded files for a session."""
    session_files = _file_registry.get(session_id, {})
    return [
        {"fileId": fid, "name": info["name"], "size": info["size"]}
        for fid, info in session_files.items()
    ]


def remove_file(file_id: str, session_id: str) -> bool:
    """Remove a file from a session's registry."""
    session_files = _file_registry.get(session_id, {})
    return session_files.pop(file_id, None) is not None
