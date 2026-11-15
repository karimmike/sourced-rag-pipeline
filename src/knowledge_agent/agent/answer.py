"""Pydantic-AI agent: searches the index, answers with checked citations, or abstains."""

import time
from dataclasses import dataclass, field

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from knowledge_agent.agent.grounding import CitationError, ground
from knowledge_agent.agent.schema import AgentAnswer, AskResult, RunStats, SourcedAnswer
from knowledge_agent.config import settings
from knowledge_agent.index.search import search
from knowledge_agent.index.store import ChunkStore
from knowledge_agent.ingestion.chunk import Chunk

INSTRUCTIONS = """\
You answer questions about the Erasmus+ Programme Guide using only the search_guide tool.
- Search before answering. If the results do not cover the question, rephrase and search again.
- Answer only from the returned chunks, never from your own knowledge.
- For every claim, cite the chunk_id and a quote copied exactly from that chunk's text.
- If the chunks do not support an answer, set enough_evidence to false, give no citations,
  and say in the answer what information is missing.
- Answer in the language of the question; quotes stay in the guide's original wording.
"""

UNVERIFIED_ANSWER = "The answer could not be verified against the sources."
# Backstop against runaway runs; a normal run is max_searches + one answer + one retry.
# Hitting it raises UsageLimitExceeded: it is a failure, not an abstention.
USAGE_LIMITS = UsageLimits(request_limit=10, total_tokens_limit=150_000)


@dataclass
class Deps:
    store: ChunkStore
    max_searches: int
    searches: int = 0
    # Only chunks returned in this run can be cited.
    retrieved: dict[str, Chunk] = field(default_factory=dict)
    # Set by the output validator so ask() can tell a failed citation check from other model errors.
    citation_check_failed: bool = False


agent = Agent(
    output_type=AgentAnswer,
    deps_type=Deps,
    instructions=INSTRUCTIONS,
    # Separate budgets, so a failed tool call cannot use up the citation retry.
    retries={"tools": 1, "output": 1},
)


@agent.tool
def search_guide(ctx: RunContext[Deps], query: str) -> list[dict[str, str]] | str:
    """Search the Erasmus+ Programme Guide and return the most relevant chunks."""
    deps = ctx.deps
    if deps.searches >= deps.max_searches:
        return "Search limit reached. Answer from the chunks you already have, or abstain."
    deps.searches += 1
    results = []
    for chunk, _score in search(deps.store, query, top_k=settings.top_k):
        deps.retrieved[chunk.id] = chunk
        results.append(
            {"chunk_id": chunk.id, "heading_path": " > ".join(chunk.heading_path), "text": chunk.text}
        )
    return results


@agent.output_validator
def check_citations(ctx: RunContext[Deps], answer: AgentAnswer) -> AgentAnswer:
    try:
        ground(answer, ctx.deps.retrieved)
    except CitationError as error:
        ctx.deps.citation_check_failed = True
        raise ModelRetry(
            f"Citation check failed: {error}. Quote exactly from the cited chunk, or abstain."
        ) from error
    ctx.deps.citation_check_failed = False
    return answer


def ask(question: str, store: ChunkStore, model: Model | None = None) -> AskResult:
    """Answer question from the index with checked citations, or abstain.

    A citation check that still fails after the retry becomes an abstention. Hitting
    USAGE_LIMITS raises UsageLimitExceeded; other model errors are raised too.
    """
    deps = Deps(store=store, max_searches=settings.max_searches)
    usage = RunUsage()
    start = time.perf_counter()
    try:
        result = agent.run_sync(
            question,
            model=model if model is not None else _default_model(),
            deps=deps,
            usage=usage,
            usage_limits=USAGE_LIMITS,
        )
        sourced = ground(result.output, deps.retrieved)
    except UnexpectedModelBehavior:
        if not deps.citation_check_failed:
            raise
        sourced = SourcedAnswer(
            answer=UNVERIFIED_ANSWER,
            sources=[],
            enough_evidence=False,
            abstain_reason="citation_check_failed",
        )
    stats = RunStats(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        searches=deps.searches,
        elapsed_seconds=time.perf_counter() - start,
    )
    return AskResult(answer=sourced, stats=stats)


def _default_model() -> Model:
    if settings.anthropic_api_key is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; add it to .env")
    # pydantic-settings reads .env without exporting it, so the provider cannot find the key itself.
    provider = AnthropicProvider(api_key=settings.anthropic_api_key.get_secret_value())
    return AnthropicModel(settings.llm_model, provider=provider)
