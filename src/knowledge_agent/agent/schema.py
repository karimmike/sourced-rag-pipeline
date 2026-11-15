"""Answer models: what the model returns and what callers receive."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# Docstrings and field descriptions of Citation and AgentAnswer are sent to the model.
class Citation(BaseModel):
    """One piece of evidence for the answer."""

    chunk_id: str = Field(description="The chunk_id of a chunk returned by search_guide in this conversation.")
    quote: str = Field(
        description="One continuous passage copied character for character from that chunk's text. "
        "Do not paraphrase, translate, shorten inside, or join separate passages."
    )


class AgentAnswer(BaseModel):
    """Your final answer to the question."""

    answer: str = Field(
        description="The answer, written in the same language as the question. "
        "If enough_evidence is false, say what information is missing."
    )
    citations: list[Citation] = Field(description="One citation per claim. Empty if enough_evidence is false.")
    enough_evidence: bool = Field(description="True only if the cited chunks support every claim in the answer.")

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
