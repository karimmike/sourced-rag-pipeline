import hashlib
from collections.abc import Sequence


class FakeEmbedder:
    """Deterministic stand-in for FastEmbedEmbedder: no model, no network."""

    model_name = "fake-embedder"
    dimension = 8

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [byte / 255 for byte in hashlib.sha256(text.encode("utf-8")).digest()[: self.dimension]]
            for text in texts
        ]

    def count_tokens(self, text: str) -> int:
        return len(text.split())
