"""In-memory chat history store."""

import uuid
from datetime import datetime, timezone


_history: list[dict] = []


def add_message(role: str, content: str, sources: list | None = None) -> dict:
    """Append a message to history and return it."""
    entry = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": sources or [],
    }
    _history.append(entry)
    return entry


def get_history() -> list[dict]:
    """Return the full conversation history."""
    return list(_history)


def clear() -> None:
    """Reset the history."""
    _history.clear()
