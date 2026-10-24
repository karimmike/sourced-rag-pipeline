"""Settings read from environment variables, with defaults for local development."""

import os

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
