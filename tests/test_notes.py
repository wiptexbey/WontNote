"""
test_notes.py — WontNote Note Operations Test Suite
===================================================
Tests for create_note and update_note functions in wontnote/notes.py.
"""

import time
from wontnote.notes import create_note, update_note


def test_create_note_structure():
    """create_note generates a valid dictionary with uuid, title, content, and ISO timestamps."""
    note = create_note(title="Meeting Notes", content="Discuss Q4 roadmap.")
    assert isinstance(note, dict)
    assert "id" in note
    assert len(note["id"]) == 36  # UUID4 string representation length
    assert note["title"] == "Meeting Notes"
    assert note["content"] == "Discuss Q4 roadmap."
    assert "created" in note
    assert "modified" in note
    assert note["created"] == note["modified"]


def test_update_note_fields_and_timestamp():
    """update_note updates title and/or content and updates the modified timestamp."""
    note = create_note(title="Initial", content="Draft")
    initial_modified = note["modified"]

    time.sleep(0.01)  # Ensure clock advances

    updated = update_note(note, title="Updated Title")
    assert updated["title"] == "Updated Title"
    assert updated["content"] == "Draft"  # Content unchanged
    assert updated["modified"] >= initial_modified

    second_modified = updated["modified"]
    time.sleep(0.01)

    updated_again = update_note(updated, content="Final Content")
    assert updated_again["title"] == "Updated Title"
    assert updated_again["content"] == "Final Content"
    assert updated_again["modified"] >= second_modified
