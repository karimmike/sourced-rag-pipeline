"""Semantic search over indexed chunks, limited to chunks the caller may see."""

from qdrant_client import models

from knowledge_agent.index.store import ChunkStore, point_to_chunk
from knowledge_agent.ingestion.chunk import Chunk

# No user accounts yet, so every caller may see public chunks only.
ALLOWED_ACCESS = ["public"]


def search(
    store: ChunkStore, query: str, top_k: int = 5, source: str | None = None
) -> list[tuple[Chunk, float]]:
    """The top_k chunks most similar to query, best first, with cosine scores."""
    conditions = [models.FieldCondition(key="access", match=models.MatchAny(any=ALLOWED_ACCESS))]
    if source is not None:
        conditions.append(models.FieldCondition(key="source", match=models.MatchValue(value=source)))
    points = store.client.query_points(
        store.collection,
        query=store.embedder.embed_query(query),
        query_filter=models.Filter(must=conditions),
        limit=top_k,
        with_payload=True,
    ).points
    return [(point_to_chunk(point), point.score) for point in points]
