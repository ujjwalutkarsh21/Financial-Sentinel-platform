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
    Monkey-patch knowledge.vector_db.upsert() to work with both Agno API versions.

    The internal Agno caller passes arguments POSITIONALLY:
        upsert(documents, content_hash)   ← new Agno
        upsert(documents)                 ← old Agno

    Documents may be Agno Document objects OR plain strings depending on the
    Agno version / reader used.  We guard all attribute assignments accordingly.

    Calling this multiple times on the same instance is safe (idempotent guard).
    """
    vector_db = knowledge.vector_db

    # Guard: don't double-patch
    if getattr(vector_db, "_upsert_patched", False):
        return

    original_upsert = vector_db.upsert

    def _safe_upsert(*args, **kwargs):
        # Normalise: extract documents however they arrived
        if args:
            documents = args[0]
            rest_args = args[1:]
        else:
            documents = kwargs.pop("documents", [])
            rest_args = ()

        # Stamp each document with a content_hash attribute if absent.
        # Guard against plain str objects — you cannot set attributes on str.
        for doc in documents:
            if isinstance(doc, str):
                # Raw string — nothing to stamp; the combined hash below covers it
                continue
            if not getattr(doc, "content_hash", None):
                try:
                    doc.content_hash = _content_hash(getattr(doc, "content", "") or "")
                except (AttributeError, TypeError):
                    # Some object types don't allow attribute assignment — skip silently
                    pass

        try:
            # Try calling with original positional/keyword args unchanged
            return original_upsert(documents, *rest_args, **kwargs)
        except TypeError as first_err:
            # If that failed, try the opposite arity:
            # new API needs content_hash, old API doesn't want it
            combined_hash = _content_hash(
                "".join(
                    (doc if isinstance(doc, str) else getattr(doc, "content", "")) or ""
                    for doc in documents
                )
            )
            try:
                # New API: pass content_hash as second positional arg
                return original_upsert(documents, combined_hash)
            except TypeError:
                try:
                    # Old API: documents only
                    return original_upsert(documents)
                except TypeError:
                    # Give up and re-raise the original error
                    raise first_err

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
    3. Call knowledge.insert(path, reader) — same pattern as load_kb.py.
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
        try:
            logger.info("Adding content from path, %s, None,\n     %s, None", file_id, path)
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