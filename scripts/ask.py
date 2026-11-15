"""Ask one question about the Erasmus+ guide and print the answer with its sources."""

import os

# Must be set before pydantic_ai is imported.
os.environ["PYDANTIC_AI_NO_BANNER"] = "1"

import argparse  # noqa: E402
import sys  # noqa: E402

from pydantic_ai.exceptions import UsageLimitExceeded  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402

from knowledge_agent.agent.answer import ask  # noqa: E402
from knowledge_agent.config import settings  # noqa: E402
from knowledge_agent.index.embed import FastEmbedEmbedder  # noqa: E402
from knowledge_agent.index.store import ChunkStore  # noqa: E402
from knowledge_agent.pricing import estimate_cost  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args()
    # Piped output on Windows defaults to cp1252, which cannot print every character in the guide.
    sys.stdout.reconfigure(encoding="utf-8")

    store = ChunkStore(QdrantClient(url=settings.qdrant_url), FastEmbedEmbedder())
    # Without this, an empty index looks like an abstention and still costs a model call.
    if store.client.count(store.collection).count == 0:
        sys.exit("The index is empty. Run python scripts/ingest.py first.")
    try:
        result = ask(args.question, store)
    except UsageLimitExceeded as error:
        sys.exit(f"Run stopped by the usage limit: {error}")

    if args.json:
        print(result.model_dump_json(indent=2))
        return

    answer, stats = result.answer, result.stats
    print(answer.answer)
    if answer.enough_evidence:
        print("\nSources:")
        for i, source in enumerate(answer.sources, start=1):
            print(f"  [{i}] {' > '.join(source.heading_path)} ({source.version})")
            print(f'      "{source.quote}"')
            print(f"      {source.uri}")
    else:
        print(f"\nAbstained: {answer.abstain_reason}")

    cost = estimate_cost(settings.llm_model, stats.input_tokens, stats.output_tokens)
    cost_text = f"~${cost:.4f}" if cost is not None else "cost unknown (no price listed)"
    print(
        f"\n{settings.llm_model}: {stats.searches} searches, "
        f"{stats.input_tokens:,} input / {stats.output_tokens:,} output tokens, "
        f"{stats.elapsed_seconds:.1f} s, {cost_text}"
    )


if __name__ == "__main__":
    main()
