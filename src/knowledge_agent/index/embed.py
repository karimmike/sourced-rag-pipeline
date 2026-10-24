"""Text embeddings for indexing, and the matching token counter for the chunker."""

from collections.abc import Sequence
from typing import Protocol

from fastembed import TextEmbedding
from tokenizers import Tokenizer

MODEL_NAME = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    """What the store needs from an embedding model; tests use a fake."""

    model_name: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    def count_tokens(self, text: str) -> int: ...


class FastEmbedEmbedder:
    """bge-small-en-v1.5 on the CPU through FastEmbed; downloads the model once."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = TextEmbedding(model_name)
        self.dimension = self._model.embedding_size
        # FastEmbed's tokenizer truncates at 512, which would hide oversized chunks; we
        # count on an untruncated, unpadded copy so the embedding input stays protected.
        self._tokenizer = Tokenizer.from_str(self._model.model.tokenizer.to_str())
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(list(texts))]

    def count_tokens(self, text: str) -> int:
        # Includes [CLS] and [SEP], which count toward the model's 512-token limit.
        return len(self._tokenizer.encode(text).ids)
