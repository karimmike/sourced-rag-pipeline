"""Check the model's citations against the chunks retrieved in this run."""

from collections.abc import Mapping

from knowledge_agent.agent.schema import AgentAnswer, Source, SourcedAnswer
from knowledge_agent.ingestion.chunk import Chunk


class CitationError(ValueError):
    """Raised by ground() when any citation fails; the message lists every problem."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def ground(answer: AgentAnswer, retrieved: Mapping[str, Chunk]) -> SourcedAnswer:
    """Resolve every citation to a retrieved chunk, or raise CitationError listing all failures.

    retrieved holds only the chunks returned in this run, so a citation to any other chunk fails.
    """
    if not answer.enough_evidence:
        return SourcedAnswer(
            answer=answer.answer,
            sources=[],
            enough_evidence=False,
            abstain_reason="insufficient_evidence",
        )

    problems = []
    sources = []
    for i, citation in enumerate(answer.citations, start=1):
        chunk = retrieved.get(citation.chunk_id)
        quote = _normalise(citation.quote)
        if chunk is None:
            problems.append(f"citation {i}: chunk {citation.chunk_id!r} was not retrieved in this run")
        elif not quote:
            problems.append(f"citation {i}: quote is empty")
        elif quote not in _normalise(chunk.text):
            problems.append(f"citation {i}: quote not found in chunk {citation.chunk_id!r}")
        else:
            sources.append(
                Source(
                    chunk_id=chunk.id,
                    quote=citation.quote,
                    source=chunk.source,
                    heading_path=chunk.heading_path,
                    uri=chunk.uri,
                    version=chunk.version,
                )
            )
    if problems:
        raise CitationError(problems)
    return SourcedAnswer(answer=answer.answer, sources=sources, enough_evidence=True)


def _normalise(text: str) -> str:
    return " ".join(text.split())
