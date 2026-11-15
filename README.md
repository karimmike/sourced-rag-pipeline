# sourced-rag-pipeline

A retrieval pipeline that answers questions from documents with citations to the retrieved
passages, or states that there is not enough evidence to answer.

## Why this project

## Status

| Component                                     | State       |
|-----------------------------------------------|-------------|
| Connector for the Erasmus+ Programme Guide    | Works       |
| HTML parsing (headings, tables, footnotes)    | Works       |
| Structure-aware chunking with source metadata | Works       |
| Qdrant index with incremental per-source sync | Works       |
| Vector search                                 | Works       |
| Agent with citations checked in code          | In progress |
| Evaluation set and baseline                   | Planned     |
| HTTP API                                      | Planned     |

## Quickstart

Requires Python 3.12+ and Docker.

    docker compose up -d                 # Qdrant on localhost:6333
    cp .env.example .env                 # then add your ANTHROPIC_API_KEY (used by the agent only)
    python -m venv .venv
    .venv\Scripts\activate               # Windows
    source .venv/bin/activate            # macOS/Linux
    pip install -e ".[dev]"
    python scripts/ingest.py             # downloads the guide pages, chunks and indexes them
    pytest                               # unit tests; integration tests: pytest -m integration

`ingest.py --refresh` downloads the pages again; `--full` re-chunks every document.

## Design principles

- Abstention is an explicit decision (`enough_evidence = false`), not a timeout or a fallback.
- Citations are checked in code against the retrieved chunks, not trusted from the model.
- Every chunk keeps its source, section, URL and edition.
- Every change to retrieval or prompts is measured with the evaluation in `eval/`.

Details on the demo corpus: [ADR 001](docs/decisions/001-demo-corpus.md).

## Data and license

The demo corpus is fetched at ingestion time and is not stored in this repository.

> Source: European Commission, *Erasmus+ Programme Guide 2026*, Version 1 (12.11.2025),
> © European Union, CC BY 4.0. Content extracted and chunked.

The code is released under the [MIT License](LICENSE).
