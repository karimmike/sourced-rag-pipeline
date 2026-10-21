# sourced-rag-pipeline

A RAG pipeline that retrieves from documents and answers with sources, or says there isn't
enough evidence. Built as a reusable knowledge-retrieval layer that other agents can call as
a tool, with pluggable connectors (later: Google Drive, HubSpot, SQL databases).
Author: Karim Mike Rahhal. Public portfolio project.

## Working agreement
I'm building this project myself, step by step.
- Never create or edit files without showing me the change and getting my approval.
- One small step at a time. Before writing code, explain what it does and why.
- When I write code myself, review it: point out bugs and simpler options, but don't
  rewrite it unless I ask.
- Keep changes small enough that I can understand every line.
- Don't commit or push; I do that myself.

## Fixed decisions
- Python package: src/knowledge_agent/. Agent: Pydantic-AI. Vector store: Qdrant.
- Every answer has citations to retrieved chunks, or enough_evidence = false.
  Abstention is an explicit decision, never a timeout.
- Every change to retrieval or prompts is measured with the evaluation in eval/.
- Demo corpus: public documents only (Erasmus+ Programme Guide). Never commit secrets,
  private data or large documents.

## Reference material (learning only, never copy)
complex-RAG-guide (FareedKhan-dev, Apache-2.0) was studied separately as a reference; it is
not part of this repository. Lessons we apply because the reference got them wrong:
- Abstention there was a 45-step recursion-limit timeout; ours must be a real decision.
- Its only deterministic grounding check was dead code; ours checks citations in code.
- Its chunks and quotes carried almost no source metadata; ours keep source, section,
  URL/page and edition on every chunk.
- It had no evaluation baseline; we measure from the first version.
- Unpinned and missing dependencies; we pin versions.

## Structure
- connectors/: one interface (base.py) every source follows; local_files.py first.
- ingestion/: parse, structure-aware chunking with metadata, incremental sync.
- index/: embeddings and Qdrant store.
- agent/: Pydantic-AI agent, retrieval tool, answer schema
  (answer, citations, enough_evidence).
- api/: FastAPI endpoint (later). eval/: test set and evaluation. tests/: unit tests.
- scripts/: ingest.py, ask.py.