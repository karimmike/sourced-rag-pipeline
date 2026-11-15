"""Settings from environment variables and .env, with defaults for local development."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# parents[2] is the repository root, as long as the package is installed in editable mode.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Field names map to upper-case environment variables, e.g. qdrant_url -> QDRANT_URL."""

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    fastembed_cache_path: str = str(PROJECT_ROOT / ".cache" / "fastembed")
    # Optional because only the agent needs it; ingestion and tests run without a key.
    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-sonnet-5-5"
    top_k: int = 5
    max_searches: int = 3


settings = Settings()
