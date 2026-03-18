"""Ingestion service — reads uploaded PDFs and inserts them into a session-scoped LanceDB Knowledge base."""

import hashlib
import logging

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from services import upload_service

logger = logging.getLogger(__name__)

_pdf_reader = PDFReader()


def _content_hash(text: str) -> str:
    """SHA-256 hash of document text — required by newer Agno LanceDb.upsert()."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _patch_vector_db_upsert(knowledge: Knowledge) -> None:
    """
    Monkey-patch knowledge.vector_db.upsert() to work with both Agno versions.

    Agno >= 1.4.x changed LanceDb.upsert() to require a `content_hash` kwarg.
    This wrapper:
      - Computes and injects content_hash automatically when missing.
      - Tries the new API first, falls back to old API on TypeError.
    Calling this multiple times on the same instance is safe (idempotent guard).
    """
    vector_db = knowledge.vector_db

    # Guard: don't double-patch
    if getattr(vector_db, "_upsert_patched", False):
        return

    original_upsert = vector_db.upsert

    def _safe_upsert(documents, content_hash=None, **kwargs):
        # Stamp each document with a content_hash attribute if absent
        for doc in documents:
            if not getattr(doc, "content_hash", None):
                doc.content_hash = _content_hash(getattr(doc, "content", "") or "")

        if content_hash is None:
            content_hash = _content_hash(
                "".join(getattr(d, "content", "") or "" for d in documents)
            )

        try:
            # New Agno API: upsert(documents, content_hash=...)
            return original_upsert(documents=documents, content_hash=content_hash, **kwargs)
        except TypeError:
            # Old Agno API: upsert(documents)
            return original_upsert(documents=documents, **kwargs)

    vector_db.upsert = _safe_upsert
    vector_db._upsert_patched = True


def ingest_files_for_session(
    session_id: str,
    attachments: list[str],
    knowledge: Knowledge,
) -> list[str]:
    """
    For each file_id in *attachments* that hasn't been indexed yet:

    1. Look up the local path via upload_service.
    2. Patch the LanceDB upsert for content_hash API compatibility.
    3. Call knowledge.insert(path, reader) — the same pattern used in load_kb.py.
    4. Mark the file as indexed so it won't be re-embedded on subsequent messages.

    Returns a list of human-readable warning strings for files that
    could not be read (corrupt, image-only, missing, etc.).
    """
    warnings: list[str] = []

    # Patch upsert once per knowledge instance (idempotent)
    _patch_vector_db_upsert(knowledge)

    for file_id in attachments:
        # --- already indexed? skip ---
        if upload_service.is_indexed(file_id):
            logger.info("File %s already indexed — skipping.", file_id)
            continue

        # --- look up path ---
        path = upload_service.get_file_path(file_id, session_id)
        if path is None:
            msg = f"File {file_id} not found in session {session_id}."
            logger.warning(msg)
            warnings.append(msg)
            continue

        filename = upload_service.get_file_name(file_id, session_id) or file_id

        # --- read & embed using knowledge.insert() ---
        # This matches the working pattern in load_kb.py:
        #   knowledge.insert(path=path, reader=PDFReader())
        try:
            logger.info("Ingesting '%s' (id=%s) from %s", filename, file_id, path)
            knowledge.insert(path=path, reader=_pdf_reader)
            upload_service.mark_indexed(file_id)
            logger.info("Successfully indexed '%s'", filename)

        except Exception as exc:
            err_str = str(exc).lower()

            if any(kw in err_str for kw in ("blank", "image", "no text", "skipped", "no pages")):
                msg = (
                    f"'{filename}' appears to contain only images or blank pages. "
                    "Please upload a text-based PDF for best results."
                )
            else:
                msg = (
                    f"Could not process '{filename}'. "
                    "It may be corrupt, password-protected, or not a valid PDF."
                )

            logger.exception("Failed to ingest file %s", file_id)
            warnings.append(msg)

    return warnings