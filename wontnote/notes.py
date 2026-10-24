"""
notes.py — WontNote Note Data Operations
========================================
Helpers for creating and updating notes.
"""

from datetime import datetime, timezone
import uuid


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def create_note(title: str = "", content: str = "") -> dict:
    """
    Create a new note object.

    Note data model: id (uuid4), title, content, created, modified.
    """
    now = _utc_now_iso()
    return {
        "id":       str(uuid.uuid4()),
        "title":    title,
        "content":  content,
        "created":  now,
        "modified": now,
    }


def update_note(
    note: dict,
    title: str | None = None,
    content: str | None = None,
) -> dict:
    """Update an existing note's title and/or content; refresh the modified timestamp."""
    if title is not None:
        note["title"] = title
    if content is not None:
        note["content"] = content
    note["modified"] = _utc_now_iso()
    return note
