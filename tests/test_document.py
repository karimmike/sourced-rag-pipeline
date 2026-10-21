from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from knowledge_agent.connectors.base import Document


def make_document(**overrides) -> Document:
    """Build a Document with only the required fields; overrides replace values."""
    fields = {
        "id": "doc-1",
        "title": "Erasmus+ Programme Guide",
        "source": "local_files",
        "content": "Who can participate",
        "uri": "https://example.org/guide.html",
        "content_type": "text/html",
        "fetched_at": datetime(2026, 10, 17, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return Document(**fields)


def test_create_with_required_fields_only():
    doc = make_document()

    assert doc.id == "doc-1"
    assert doc.content == "Who can participate"


def test_access_and_metadata_defaults():
    doc = make_document()

    assert doc.access == ("public",)
    assert doc.metadata == {}


def test_checksum_depends_on_content():
    same_a = make_document(content="Who can participate")
    same_b = make_document(content="Who can participate")
    different = make_document(content="Eligible countries")

    assert same_a.checksum == same_b.checksum
    assert same_a.checksum != different.checksum


def test_document_is_frozen():
    doc = make_document()

    with pytest.raises(ValidationError):
        doc.title = "Changed"
