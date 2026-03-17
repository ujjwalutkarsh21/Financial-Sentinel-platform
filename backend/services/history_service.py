"""In-memory chat history store — scoped per session ID."""

import uuid
from datetime import datetime, timezone


_history: dict[str, list[dict]] = {}


def add_message(session_id: str, role: str, content: str, sources: list | None = None) -> dict:
    """Append a message to a session's history and return it."""
    entry = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": sources or [],
    }
    _history.setdefault(session_id, []).append(entry)
    return entry


def get_history(session_id: str) -> list[dict]:
    """Return the conversation history for a specific session."""
    return list(_history.get(session_id, []))


def clear(session_id: str | None = None) -> None:
    """Clear history for a session, or all sessions if no ID given."""
    if session_id:
        _history.pop(session_id, None)
    else:
        _history.clear()
