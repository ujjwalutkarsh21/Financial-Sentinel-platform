"""File upload service — saves to backend/tmp/uploads/ and tracks IDs per session."""

import os
import uuid
import json
import logging

from fastapi import UploadFile
from schemas.chat_schema import UploadResponse

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "uploads")
REGISTRY_FILE = os.path.join(UPLOAD_DIR, "registry.json")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory mapping: session_id → { fileId → {path, name, size} }
_file_registry: dict[str, dict[str, dict]] = {}
# Tracks file_ids that have already been embedded into LanceDB
_indexed_files: set[str] = set()


def _save_registry():
    """Persist registry to disk."""
    try:
        with open(REGISTRY_FILE, "w") as f:
            json.dump({
                "registry": _file_registry,
                "indexed": list(_indexed_files)
            }, f)
    except Exception as e:
        logger.error("Failed to save registry: %s", e)


def _load_registry():
    """Load registry from disk on startup."""
    global _file_registry, _indexed_files
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r") as f:
                data = json.load(f)
                _file_registry = data.get("registry", {})
                _indexed_files = set(data.get("indexed", []))
                logger.info("Loaded registry: %d sessions, %d indexed files", len(_file_registry), len(_indexed_files))
        except Exception as e:
            # Don't fail the whole app if registry is corrupt, but log it
            logger.error("Failed to load registry: %s", e)

# Initial load on module import
_load_registry()


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
    _save_registry()

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
    result = session_files.pop(file_id, None) is not None
    if result:
        _save_registry()
    return result


# ── Indexing helpers (used by ingestion_service) ──────────────────────

def is_indexed(file_id: str) -> bool:
    """Return True if this file has already been embedded into LanceDB."""
    return file_id in _indexed_files


def mark_indexed(file_id: str) -> None:
    """Record that a file has been successfully embedded."""
    _indexed_files.add(file_id)
    _save_registry()


def get_file_name(file_id: str, session_id: str) -> str | None:
    """Return the original filename for a given file_id, or None."""
    session_files = _file_registry.get(session_id, {})
    entry = session_files.get(file_id)
    return entry["name"] if entry else None


def clear_all_files() -> None:
    """
    Delete every uploaded file from disk and clear all in-memory state.
    Called by the reset endpoint when the user clicks Exit.
    """
    # Remove files from disk
    for session_files in _file_registry.values():
        for info in session_files.values():
            try:
                path = info.get("path", "")
                if path and os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass

    _file_registry.clear()
    _indexed_files.clear()
    if os.path.exists(REGISTRY_FILE):
        try:
            os.remove(REGISTRY_FILE)
        except OSError:
            pass
