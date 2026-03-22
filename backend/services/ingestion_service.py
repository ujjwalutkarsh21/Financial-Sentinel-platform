"""
Ingestion service — reads uploaded PDFs and inserts them into a
session-scoped LanceDB Knowledge base.

Root cause of the Gemini 400 error
───────────────────────────────────
Agno's PDFReader extracts some pages as empty strings (cover pages,
image-only pages, pure-whitespace pages).  When these reach Gemini's
embedding API it returns:

    400 INVALID_ARGUMENT: EmbedContentRequest.content contains an empty Part.

The fix is applied at TWO levels so it can't be bypassed:

  Level 1 — patch knowledge.vector_db.upsert() to silently drop any doc
             whose content is empty / whitespace-only before the batch
             reaches the embedder.

  Level 2 — patch the embedder's get_embedding() directly so even if Agno
             changes its internal call path, empty strings are blocked.
"""

import hashlib
import logging
from typing import Any

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from services import upload_service

logger = logging.getLogger(__name__)

_pdf_reader = PDFReader()


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _doc_content(doc: Any) -> str:
    if isinstance(doc, str):
        return doc
    return getattr(doc, "content", "") or ""


def _is_empty(doc: Any) -> bool:
    return not _doc_content(doc).strip()


# ─────────────────────────────────────────────────────────────────────
# Level-1 patch: vector_db.upsert
# ─────────────────────────────────────────────────────────────────────

def _patch_vector_db_upsert(knowledge: Knowledge) -> None:
    """
    Monkey-patch knowledge.vector_db.upsert() to drop empty documents
    before they reach the Gemini embedder.
    Safe to call multiple times (idempotent).
    """
    vector_db = knowledge.vector_db
    if getattr(vector_db, "_upsert_patched", False):
        return

    original_upsert = vector_db.upsert

    def _safe_upsert(*args, **kwargs):
        # Normalise arguments
        if args:
            documents = list(args[0])
            rest_args = args[1:]
        else:
            documents = list(kwargs.pop("documents", []))
            rest_args = ()

        # DROP empty documents
        before = len(documents)
        documents = [d for d in documents if not _is_empty(d)]
        skipped = before - len(documents)
        if skipped:
            logger.warning(
                "Dropped %d empty document(s) before embedding "
                "(prevents Gemini 'empty Part' 400 error).",
                skipped,
            )

        if not documents:
            logger.warning("All documents were empty — nothing to upsert.")
            return None

        # Stamp content_hash
        for doc in documents:
            if isinstance(doc, str):
                continue
            if not getattr(doc, "content_hash", None):
                try:
                    doc.content_hash = _content_hash(getattr(doc, "content", "") or "")
                except (AttributeError, TypeError):
                    pass

        # Try different arities (new vs old Agno)
        try:
            return original_upsert(documents, *rest_args, **kwargs)
        except TypeError:
            combined_hash = _content_hash("".join(_doc_content(d) for d in documents))
            try:
                return original_upsert(documents, combined_hash)
            except TypeError:
                try:
                    return original_upsert(documents)
                except TypeError as final_err:
                    raise final_err

    vector_db.upsert = _safe_upsert
    vector_db._upsert_patched = True
    logger.debug("Patched vector_db.upsert with empty-doc filter.")


# ─────────────────────────────────────────────────────────────────────
# Level-2 patch: embedder.get_embedding
# ─────────────────────────────────────────────────────────────────────

def _patch_embedder(knowledge: Knowledge) -> None:
    """
    Patch the embedder directly so empty strings never reach the API,
    regardless of which internal path Agno uses.
    """
    vector_db = knowledge.vector_db
    embedder = getattr(vector_db, "embedder", None)
    if embedder is None:
        return
    if getattr(embedder, "_embed_patched", False):
        return

    # Patch get_embedding (single text)
    _orig_get = getattr(embedder, "get_embedding", None)
    if _orig_get:
        def _safe_get_embedding(text: str, *a, **kw):
            if not (text or "").strip():
                logger.warning(
                    "Blocked empty string from reaching Gemini embedder (get_embedding)."
                )
                return None
            return _orig_get(text, *a, **kw)
        embedder.get_embedding = _safe_get_embedding

    # Patch get_embedding_and_usage (some Agno versions)
    _orig_usage = getattr(embedder, "get_embedding_and_usage", None)
    if _orig_usage:
        def _safe_get_embedding_and_usage(text: str, *a, **kw):
            if not (text or "").strip():
                logger.warning(
                    "Blocked empty string from reaching Gemini embedder (get_embedding_and_usage)."
                )
                return None, None
            return _orig_usage(text, *a, **kw)
        embedder.get_embedding_and_usage = _safe_get_embedding_and_usage

    embedder._embed_patched = True
    logger.debug("Patched embedder with empty-string guard.")


# ─────────────────────────────────────────────────────────────────────
# Row count helper
# ─────────────────────────────────────────────────────────────────────

def _count_rows(knowledge: Knowledge) -> int:
    """Return number of rows in the vector DB table, or 0 on any error."""
    try:
        tbl = getattr(knowledge.vector_db, "_table", None)
        if tbl is None:
            db_conn = getattr(knowledge.vector_db, "_connection", None)
            tbl_name = getattr(knowledge.vector_db, "table_name", None)
            if db_conn and tbl_name:
                try:
                    tbl = db_conn.open_table(tbl_name)
                except Exception:
                    return 0
        if tbl is not None:
            return tbl.count_rows()
    except Exception:
        pass
    return 0


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────

def ingest_files_for_session(
    session_id: str,
    attachments: list[str],
    knowledge: Knowledge,
) -> list[str]:
    """
    For each file_id in *attachments* that hasn't been indexed yet:

    1. Look up the local disk path via upload_service.
    2. Apply both Level-1 and Level-2 patches.
    3. Call knowledge.insert(path, reader).
    4. Verify rows were actually added; warn if PDF was image-only.
    5. Mark the file as indexed to skip re-embedding on future queries.

    Returns a list of human-readable warning strings for files that
    could not be embedded.
    """
    warnings: list[str] = []

    # Apply patches once per knowledge instance (idempotent)
    _patch_vector_db_upsert(knowledge)
    _patch_embedder(knowledge)

    for file_id in attachments:
        # ── Already indexed? ──────────────────────────────────────────
        if upload_service.is_indexed(file_id):
            logger.info("File %s already indexed — skipping.", file_id)
            continue

        # ── Look up path ──────────────────────────────────────────────
        path = upload_service.get_file_path(file_id, session_id)
        if path is None:
            msg = f"File {file_id} not found in session {session_id}."
            logger.warning(msg)
            warnings.append(msg)
            continue

        filename = upload_service.get_file_name(file_id, session_id) or file_id

        # Snapshot row count before insertion
        rows_before = _count_rows(knowledge)

        # ── Insert ────────────────────────────────────────────────────
        try:
            logger.info("Ingesting '%s' (session=%s)", filename, session_id)
            knowledge.insert(path=path, reader=_pdf_reader)

        except Exception as exc:
            err_str = str(exc).lower()
            if any(kw in err_str for kw in (
                "blank", "image", "no text", "skipped", "no pages",
                "empty part", "invalid_argument", "empty",
            )):
                msg = (
                    f"'{filename}' appears to be an image-based or blank PDF "
                    "and cannot be searched. Please upload a text-based (selectable-text) PDF."
                )
            else:
                msg = (
                    f"Could not process '{filename}': {str(exc)[:120]}. "
                    "It may be corrupt or password-protected."
                )
            logger.exception("Failed to ingest %s", file_id)
            warnings.append(msg)
            continue

        # ── Verify rows were actually inserted ────────────────────────
        rows_after = _count_rows(knowledge)
        new_rows = rows_after - rows_before

        if new_rows == 0:
            msg = (
                f"'{filename}' was processed but no searchable text was extracted. "
                "It is likely a scanned/image-based PDF. "
                "Please upload a text-based version for RAG analysis."
            )
            logger.warning("0 new rows inserted for '%s'.", filename)
            warnings.append(msg)
            # Don't mark indexed — user should re-upload a proper PDF
            continue

        upload_service.mark_indexed(file_id)
        logger.info(
            "Successfully indexed '%s' — %d new row(s) (total=%d).",
            filename, new_rows, rows_after,
        )

    return warnings