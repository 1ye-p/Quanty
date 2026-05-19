"""cquant.core.config — Global configuration loader.

Loads settings from environment variables and optional .env file.
Priority (highest to lowest):
  1. Environment variables (already set in shell / CI)
  2. .env file in the project root (local development)
  3. Built-in defaults

Usage::

    from cquant.core.config import settings

    print(settings.tushare_token)
    print(settings.db_path)
    print(settings.llm.anthropic_api_key)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_dotenv() -> Path | None:
    """Walk up from CWD to find the nearest .env file."""
    candidate = Path.cwd()
    for _ in range(5):
        path = candidate / ".env"
        if path.exists():
            return path
        candidate = candidate.parent
    return None


_ENV_FILE = _find_dotenv()


class DataSourceSettings(BaseSettings):
    """API keys and endpoints for market data sources."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tushare_token: SecretStr = Field(default=SecretStr(""), alias="TUSHARE_TOKEN")
    wind_user: str = Field(default="", alias="WIND_USER")
    wind_password: SecretStr = Field(default=SecretStr(""), alias="WIND_PASSWORD")
    ifind_user: str = Field(default="", alias="IFIND_USER")
    ifind_password: SecretStr = Field(default=SecretStr(""), alias="IFIND_PASSWORD")


class LLMSettings(BaseSettings):
    """API keys for LLM providers."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: SecretStr = Field(default=SecretStr(""), alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr = Field(default=SecretStr(""), alias="OPENAI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")


class StorageSettings(BaseSettings):
    """Local storage paths."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = Field(default="data/catalog.duckdb", alias="CQUANT_DB_PATH")
    lake_root: str = Field(default="data/lake", alias="CQUANT_LAKE_ROOT")
    knowledge_root: str = Field(default="knowledge", alias="CQUANT_KNOWLEDGE_ROOT")


class MLflowSettings(BaseSettings):
    """MLflow experiment tracking settings."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tracking_uri: str = Field(default="http://localhost:5000", alias="MLFLOW_TRACKING_URI")
    experiment_name: str = Field(default="cquant_default", alias="MLFLOW_EXPERIMENT_NAME")


class BacktestSettings(BaseSettings):
    """Runtime backtest defaults (override via env vars or TOML configs)."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    initial_cash: float = Field(default=1_000_000.0, alias="CQUANT_INITIAL_CASH")
    default_market: Literal["CN", "US", "HK"] = Field(default="CN", alias="CQUANT_DEFAULT_MARKET")


class CQuantSettings(BaseSettings):
    """Root settings object — compose all sub-settings here."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO", alias="CQUANT_LOG_LEVEL")
    backtest_verbose: bool = Field(default=False, alias="CQUANT_BACKTEST_VERBOSE")

    # Sub-settings (instantiated lazily to avoid import-time side effects)
    @property
    def data_source(self) -> DataSourceSettings:
        if not hasattr(self, "_data_source"):
            object.__setattr__(self, "_data_source", DataSourceSettings())
        return self._data_source  # type: ignore[return-value]

    @property
    def llm(self) -> LLMSettings:
        if not hasattr(self, "_llm"):
            object.__setattr__(self, "_llm", LLMSettings())
        return self._llm  # type: ignore[return-value]

    @property
    def storage(self) -> StorageSettings:
        if not hasattr(self, "_storage"):
            object.__setattr__(self, "_storage", StorageSettings())
        return self._storage  # type: ignore[return-value]

    @property
    def mlflow(self) -> MLflowSettings:
        if not hasattr(self, "_mlflow"):
            object.__setattr__(self, "_mlflow", MLflowSettings())
        return self._mlflow  # type: ignore[return-value]

    @property
    def backtest(self) -> BacktestSettings:
        if not hasattr(self, "_backtest"):
            object.__setattr__(self, "_backtest", BacktestSettings())
        return self._backtest  # type: ignore[return-value]

    # ── Convenience accessors ──────────────────────────────────────────────────

    @property
    def tushare_token(self) -> str:
        """Return the Tushare token as plain string (safe for SDK calls)."""
        return self.data_source.tushare_token.get_secret_value()

    @property
    def anthropic_api_key(self) -> str:
        return self.llm.anthropic_api_key.get_secret_value()

    @property
    def openai_api_key(self) -> str:
        return self.llm.openai_api_key.get_secret_value()

    @property
    def db_path(self) -> str:
        return self.storage.db_path

    @property
    def lake_root(self) -> str:
        return self.storage.lake_root


# ── Module-level singleton ─────────────────────────────────────────────────────
# Import this in any module that needs configuration:
#   from cquant.core.config import settings
settings: CQuantSettings = CQuantSettings()
