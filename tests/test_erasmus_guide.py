from pathlib import Path

import httpx
import pytest

from knowledge_agent.connectors.erasmus_guide import (
    LANDING_PATH,
    SECTION_PATHS,
    USER_AGENT,
    ErasmusGuideConnector,
    parse_landing,
)

FIXTURES = Path(__file__).parent / "fixtures" / "erasmus_guide"
PAGES_PER_FETCH = 2 + len(SECTION_PATHS)  # landing + document page + sections


def serve_fixtures(requests: list[httpx.Request]) -> httpx.Client:
    """A fake network: answers every request with a fixture page and records it."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == LANDING_PATH:
            name = "landing.html"
        elif request.url.path.startswith("/document/"):
            name = "document.html"
        else:
            name = "section.html"
        return httpx.Response(200, text=(FIXTURES / name).read_text(encoding="utf-8"))

    return httpx.Client(transport=httpx.MockTransport(handler))


def no_network() -> httpx.Client:
    """A fake network that fails the test on any request."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_builds_one_document_per_section(tmp_path):
    with serve_fixtures([]) as client, ErasmusGuideConnector(
        tmp_path, delay_seconds=0, client=client
    ) as connector:
        docs = list(connector.fetch())

    assert len(docs) == len(SECTION_PATHS)
    doc = docs[0]
    assert doc.id == "erasmus_guide:/programme-guide/part-a/participation"
    assert doc.title == "Mobility projects for higher education students and staff"
    assert doc.uri == "https://erasmus-plus.ec.europa.eu/programme-guide/part-a/participation"
    assert doc.version == "2026 v1, 12.11.2025"
    assert doc.metadata["pdf_url"] == (
        "https://erasmus-plus.ec.europa.eu/sites/default/files/2025-11/programme-guide-2026_en.pdf"
    )
    assert doc.fetched_at.tzinfo is not None


def test_downloads_once_with_user_agent_then_reuses_cache(tmp_path):
    requests = []
    with serve_fixtures(requests) as client, ErasmusGuideConnector(
        tmp_path, delay_seconds=0, client=client
    ) as connector:
        list(connector.fetch())

    assert len(requests) == PAGES_PER_FETCH
    assert all(r.headers["User-Agent"] == USER_AGENT for r in requests)

    with no_network() as client, ErasmusGuideConnector(
        tmp_path, delay_seconds=0, client=client
    ) as connector:
        assert len(list(connector.fetch())) == len(SECTION_PATHS)


def test_refresh_downloads_again(tmp_path):
    requests = []
    with serve_fixtures(requests) as client:
        with ErasmusGuideConnector(tmp_path, delay_seconds=0, client=client) as connector:
            list(connector.fetch())
        with ErasmusGuideConnector(
            tmp_path, refresh=True, delay_seconds=0, client=client
        ) as connector:
            list(connector.fetch())

    assert len(requests) == 2 * PAGES_PER_FETCH


def test_waits_between_requests(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "knowledge_agent.connectors.erasmus_guide.time.sleep", sleeps.append
    )
    with serve_fixtures([]) as client, ErasmusGuideConnector(
        tmp_path, delay_seconds=3, client=client
    ) as connector:
        list(connector.fetch())

    assert len(sleeps) == PAGES_PER_FETCH - 1
    assert all(0 < s <= 3 for s in sleeps)


def test_landing_without_version_raises():
    with pytest.raises(ValueError):
        parse_landing("<html><body><p>No edition here</p></body></html>")


def test_closes_only_its_own_client(tmp_path):
    with ErasmusGuideConnector(tmp_path) as connector:
        pass
    assert connector.client.is_closed

    with no_network() as client:
        with ErasmusGuideConnector(tmp_path, client=client):
            pass
        assert not client.is_closed
