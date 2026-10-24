"""Index the Erasmus+ guide (connector -> parse -> chunk -> Qdrant) and print a summary."""

import argparse
import random
import statistics
import sys
from pathlib import Path

from qdrant_client import QdrantClient

from knowledge_agent.config import QDRANT_URL
from knowledge_agent.connectors.erasmus_guide import ErasmusGuideConnector
from knowledge_agent.index.embed import FastEmbedEmbedder
from knowledge_agent.index.store import ChunkStore
from knowledge_agent.ingestion.chunk import chunk_document
from knowledge_agent.ingestion.parse_html import parse_html

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "public" / "erasmus_guide"
# bge-small-en-v1.5 ignores everything past 512 tokens.
MODEL_LIMIT = 512
SAMPLES = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="re-chunk every document, e.g. after a chunker change"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="download the pages again instead of using the cache"
    )
    args = parser.parse_args()
    # Piped output on Windows defaults to cp1252, which cannot print every character in the guide.
    sys.stdout.reconfigure(encoding="utf-8")

    embedder = FastEmbedEmbedder()
    store = ChunkStore(QdrantClient(url=QDRANT_URL), embedder)
    with ErasmusGuideConnector(CACHE_DIR, refresh=args.refresh) as connector:
        report = store.sync(
            connector,
            lambda document: chunk_document(document, parse_html(document), embedder.count_tokens),
            full=args.full,
        )
    chunks = store.chunks(connector.name)
    if not chunks:
        sys.exit(f"No chunks indexed for {connector.name}")
    tokens = [chunk.token_count for chunk in chunks]

    print(f"Collection {store.collection} at {QDRANT_URL}")
    print(f"Documents: {report.documents} fetched, {report.skipped_documents} unchanged")
    print(
        f"Chunks: {len(chunks)} indexed; {report.added} added, "
        f"{report.unchanged} unchanged, {report.deleted} deleted"
    )
    print(
        f"Tokens per chunk: min {min(tokens)}, median {statistics.median(tokens)}, "
        f"max {max(tokens)}; over {MODEL_LIMIT}: {sum(t > MODEL_LIMIT for t in tokens)}"
    )
    # Fixed seed: both runs show the same samples, so they are easy to compare.
    for chunk in random.Random(0).sample(chunks, min(SAMPLES, len(chunks))):
        print("\n" + chunk.model_dump_json(indent=2, exclude={"text"}))
        print(chunk.text[:300] + ("..." if len(chunk.text) > 300 else ""))


if __name__ == "__main__":
    main()
