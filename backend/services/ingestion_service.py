"""Ingestion service — reads uploaded PDFs and inserts them into a session-scoped LanceDB Knowledge base."""

import logging
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from services import upload_service

logger = logging.getLogger(__name__)

_pdf_reader = PDFReader()


def ingest_files_for_session(
    session_id: str,
    attachments: list[str],
    knowledge: Knowledge,
) -> list[str]:
    """
    For each file_id in *attachments* that hasn't been indexed yet:

    1. Look up the local path via upload_service.
    2. Read & embed the PDF into the session-scoped *knowledge* (LanceDB).
    3. Mark the file as indexed so it won't be re-embedded.

    Returns a list of human-readable warning strings for files that
    could not be read (corrupt, missing, wrong format, etc.).
    """
    warnings: list[str] = []

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

        # --- read & embed ---
        try:
            logger.info("Ingesting file %s from %s", file_id, path)
            knowledge.insert(path=path, reader=_pdf_reader)
            upload_service.mark_indexed(file_id)
            logger.info("Successfully indexed file %s", file_id)
        except Exception:
            msg = f"Could not read file '{upload_service.get_file_name(file_id, session_id) or file_id}'. It may be corrupt or not a valid PDF."
            logger.exception("Failed to ingest file %s", file_id)
            warnings.append(msg)

    return warnings
