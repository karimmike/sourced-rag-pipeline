"""Connector for the HTML pages of the Erasmus+ Programme Guide (see ADR 001)."""

import re
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from knowledge_agent.connectors.base import Connector, Document

BASE_URL = "https://erasmus-plus.ec.europa.eu"
LANDING_PATH = "/programme-guide/erasmusplus-programme-guide"

SECTION_PATHS = (
    "/programme-guide/part-a/participation",
    "/programme-guide/part-b/key-action-1/higher-education-mobility-projects",
    "/programme-guide/part-b/key-action-2/cooperation-partnerships",
    "/programme-guide/part-b/key-action-2/small-scale-partnerships",
)
USER_AGENT = "sourced-rag-pipeline/0.1 (+https://github.com/karimmike/sourced-rag-pipeline)"


class ErasmusGuideConnector(Connector):
    """The ADR 001 sections of the Erasmus+ Programme Guide, cached on disk."""

    name = "erasmus_guide"

    def __init__(
        self,
        cache_dir: Path,
        refresh: bool = False,
        delay_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ):
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.delay_seconds = delay_seconds
        # Close only a client we created; a passed-in client belongs to the caller.
        self._owns_client = client is None
        self.client = client or httpx.Client(follow_redirects=True, timeout=30)
        self._last_request: float | None = None

    def __enter__(self) -> "ErasmusGuideConnector":
        return self

    def __exit__(self, *exc_info) -> None:
        if self._owns_client:
            self.client.close()

    def fetch(self) -> Iterator[Document]:
        landing, _ = self._get(LANDING_PATH)
        version_number, version_date, document_path = parse_landing(landing)
        document_page, _ = self._get(document_path)
        year, pdf_path = parse_document_page(document_page)
        version = f"{year} v{version_number}, {version_date}"
        pdf_url = urljoin(BASE_URL, pdf_path)

        for path in SECTION_PATHS:
            html, fetched_at = self._get(path)
            yield Document(
                id=f"{self.name}:{path}",
                title=page_title(html),
                source=self.name,
                content=html,
                uri=urljoin(BASE_URL, path),
                content_type="text/html",
                version=version,
                fetched_at=fetched_at,
                metadata={"pdf_url": pdf_url},
            )

    def _get(self, path: str) -> tuple[str, datetime]:
        cache_file = self.cache_dir / (path.strip("/").replace("/", "__") + ".html")
        if self.refresh or not cache_file.exists():
            self._wait()
            response = self.client.get(urljoin(BASE_URL, path), headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(response.text, encoding="utf-8")
        fetched_at = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
        return cache_file.read_text(encoding="utf-8"), fetched_at

    def _wait(self) -> None:
        """Leave at least delay_seconds between two network requests."""
        if self._last_request is not None:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.delay_seconds:
                time.sleep(self.delay_seconds - elapsed)
        self._last_request = time.monotonic()


def parse_landing(html: str) -> tuple[str, str, str]:
    """Return (version number, version date, document page path) from the landing page."""
    soup = BeautifulSoup(html, "lxml")
    match = re.search(r"Version (\d+) of (\d{2}\.\d{2}\.\d{4})", soup.get_text(" "))
    link = soup.select_one('[url*="/document/erasmus-programme-guide-"]')
    if match is None or link is None:
        raise ValueError("Landing page: edition or document link not found")
    return match.group(1), match.group(2), urlparse(link["url"]).path


def parse_document_page(html: str) -> tuple[str, str]:
    """Return (year, English PDF path) from the guide's document page."""
    download = BeautifulSoup(html, "lxml").select_one('eac-download[language="English"]')
    year = re.search(r"\b(20\d{2})\b", download["title"]) if download else None
    if year is None:
        raise ValueError("Document page: English PDF or year not found")
    return year.group(1), download["url"]


def page_title(html: str) -> str:
    """Return the page's h1 title."""
    h1 = BeautifulSoup(html, "lxml").select_one("h1.eac-page-title")
    if h1 is None:
        raise ValueError("Page title (h1.eac-page-title) not found")
    return h1.get_text(strip=True)
