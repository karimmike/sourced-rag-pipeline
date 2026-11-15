"""Answer models: what the model returns and what callers receive."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Citation(BaseModel):
    """A reference from the model's answer to one retrieved chunk."""

    # Field descriptions become part of the output schema the model sees.
    chunk_id: str = Field(description="Id of a chunk returned by the search tool in this run.")
    quote: str = Field(description="Text copied exactly from the chunk that supports the answer.")


class AgentAnswer(BaseModel):
    """What the model returns; checked by grounding.ground() before any caller sees it."""

    answer: str
    citations: list[Citation]
    enough_evidence: bool

    @model_validator(mode="after")
    def _citations_match_evidence(self) -> "AgentAnswer":
        if self.enough_evidence and not self.citations:
            raise ValueError("enough_evidence=True requires at least one citation")
        if not self.enough_evidence and self.citations:
            raise ValueError("an abstention (enough_evidence=False) must not have citations")
        return self


class Source(BaseModel):
    """A citation resolved against the stored chunk; metadata never comes from the model."""

    chunk_id: str
    quote: str
    source: str
    heading_path: tuple[str, ...]
    uri: str
    version: str | None


AbstainReason = Literal["insufficient_evidence", "citation_check_failed"]


class SourcedAnswer(BaseModel):
    """What callers receive: a grounded answer with sources, or an abstention with its reason."""

    answer: str
    sources: list[Source]
    enough_evidence: bool
    abstain_reason: AbstainReason | None = None


class RunStats(BaseModel):
    """Cost and latency of one ask() call, for ask.py and the eval."""

    input_tokens: int
    output_tokens: int
    searches: int
    elapsed_seconds: float


class AskResult(BaseModel):
    """What ask() returns: the answer for callers, plus stats for reporting."""

    answer: SourcedAnswer
    stats: RunStats
