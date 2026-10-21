import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class Document(BaseModel):
    """One item from a source, before chunking (for example, one HTML page)."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    source: str
    content: str
    uri: str
    content_type: str
    version: str | None = None
    fetched_at: datetime
    source_updated_at: datetime | None = None
    access: tuple[str, ...] = ("public",)
    # Treat as read-only: frozen=True does not protect dict contents.
    metadata: dict[str, str] = Field(default_factory=dict)

    @computed_field
    @property
    def checksum(self) -> str:
        """Fingerprint of the content, used to detect changes."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class Connector(ABC):
    """A source of Documents. Every connector (local files, web, Drive, SQL) follows this."""

    name: str

    @abstractmethod
    def fetch(self) -> Iterator[Document]:
        """Yield every Document currently in the source."""