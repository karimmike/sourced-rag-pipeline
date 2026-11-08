"""Settings read from environment variables, with defaults for local development."""

import os
from pathlib import Path

# parents[2] is the repository root, as long as the package is installed in editable mode.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
FASTEMBED_CACHE_DIR = os.environ.get("FASTEMBED_CACHE_PATH", str(PROJECT_ROOT / ".cache" / "fastembed"))
