"""
Settings — pydantic-settings with .env support.
All config lives here; never scatter os.getenv calls.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server identity ---
    server_name: str = "aiwatcher-mcp"
    server_version: str = "0.1.6"
    backend_port: int = Field(default=10946, alias="BACKEND_PORT")
    frontend_port: int = Field(default=10947, alias="FRONTEND_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # When set, REST routes require X-AIWatcher-Key or Authorization: Bearer (health + /mcp exempt)
    api_key: str = Field(default="", alias="AIWATCHER_API_KEY")

    # --- Database ---
    db_path: str = Field(default="data/aiwatcher.db", alias="DB_PATH")

    # --- Feed polling ---
    feed_poll_interval_minutes: int = Field(default=30, alias="FEED_POLL_INTERVAL_MINUTES")
    max_items_per_feed: int = Field(default=50, alias="MAX_ITEMS_PER_FEED")

    # --- LLM Provider (lmstudio | ollama | deepseek | anthropic) ---
    # Local-first: lmstudio and ollama are always allowed (no API key needed).
    # Cloud providers (deepseek, anthropic) require CLOUD_PROVIDERS_ALLOWED + API key.
    llm_provider: str = Field(default="lmstudio", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")  # e.g. http://localhost:11434/v1

    # --- Cloud provider allow-matrix ---
    # Comma-separated list of cloud providers allowed for distillation.
    # Empty = local-only (ollama/lmstudio). Set to "deepseek" or "deepseek,anthropic"
    # to enable cloud API calls. This gates ALL cloud usage — if a provider isn't
    # listed here, its API key is ignored and calls fall back to local.
    cloud_providers_allowed: str = Field(default="", alias="CLOUD_PROVIDERS_ALLOWED")

    # --- DeepSeek (V4 Flash $0.14/M in, $0.28/M out — cheapest cloud option) ---
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")

    # --- Anthropic (Claude — expensive, quality-critical only) ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    distillation_model: str = Field(default="deepseek-v4-flash", alias="DISTILLATION_MODEL")
    distillation_interval_hours: int = Field(default=6, alias="DISTILLATION_INTERVAL_HOURS")
    digest_cache_ttl_minutes: int = Field(default=60, alias="DIGEST_CACHE_TTL_MINUTES")
    feed_decay_days: int = Field(default=30, alias="FEED_DECAY_DAYS")
    feed_decay_min_items: int = Field(default=5, alias="FEED_DECAY_MIN_ITEMS")
    feed_decay_urgency_threshold: float = Field(default=2.0, alias="FEED_DECAY_URGENCY_THRESHOLD")
    portfolio_watch_terms: str = Field(
        default="fastmcp,anthropic,openai,cursor,mcp fleet,windsurf,zed,auto-review,mcp approval,memops,changelog",
        alias="PORTFOLIO_WATCH_TERMS",
    )
    portfolio_watch_urgency_boost: float = Field(default=1.0, alias="PORTFOLIO_WATCH_URGENCY_BOOST")
    digest_tone_sandra: str = Field(
        default="Technical depth: MCP fleet, tooling, Vienna ops.",
        alias="DIGEST_TONE_SANDRA",
    )
    digest_tone_steve: str = Field(
        default="Accessible summary for a retired bank IT reader.",
        alias="DIGEST_TONE_STEVE",
    )

    # --- Tiered distillation (flash-first for cost efficiency) ---
    # When enabled: all items scored by cheap flash model first.
    # Only borderline items (relevance 4-7) get re-scored by the pro model.
    distillation_flash_enabled: bool = Field(default=False, alias="DISTILLATION_FLASH_ENABLED")
    distillation_flash_provider: str = Field(
        default="lmstudio", alias="DISTILLATION_FLASH_PROVIDER"
    )
    distillation_flash_model: str = Field(default="gemma-3-1b-it", alias="DISTILLATION_FLASH_MODEL")
    distillation_flash_base_url: str = Field(default="", alias="DISTILLATION_FLASH_BASE_URL")
    # Borderline range: items with relevance in [min, max] get re-scored by pro model
    distillation_borderline_min: float = Field(default=4.0, alias="DISTILLATION_BORDERLINE_MIN")
    distillation_borderline_max: float = Field(default=7.0, alias="DISTILLATION_BORDERLINE_MAX")

    @property
    def allowed_cloud_providers(self) -> set[str]:
        """Parsed set of allowed cloud providers."""
        if not self.cloud_providers_allowed.strip():
            return set()
        return {p.strip().lower() for p in self.cloud_providers_allowed.split(",") if p.strip()}

    def is_cloud_allowed(self, provider: str) -> bool:
        """Check if a cloud provider is in the allow-matrix."""
        return provider.lower() in self.allowed_cloud_providers

    # --- Alert thresholds ---
    # Score 0-10; items >= this wake Sandra up
    alert_threshold: float = Field(default=8.5, alias="ALERT_THRESHOLD")
    alert_hour_utc: int = Field(default=4, alias="ALERT_HOUR_UTC")  # 4 UTC = 5am Vienna
    alert_minute_utc: int = Field(default=55, alias="ALERT_MINUTE_UTC")

    # --- Speechops integration ---
    speechops_backend_url: str = Field(
        default="http://localhost:10895", alias="SPEECHOPS_BACKEND_URL"
    )
    # Direct HTTP to speechops server (separate port, fleet convention)
    speechops_http_url: str = Field(default="http://localhost:10895", alias="SPEECHOPS_HTTP_URL")

    # --- Robofang integration ---
    robofang_backend_url: str = Field(
        default="http://localhost:10871", alias="ROBOFANG_BACKEND_URL"
    )
    robofang_enabled: bool = Field(default=True, alias="ROBOFANG_ENABLED")

    # --- Email delivery (via email-mcp or SMTP) ---
    email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
    email_recipients: str = Field(
        default="sandra@example.com,steve@example.com", alias="EMAIL_RECIPIENTS"
    )
    email_subject_prefix: str = Field(default="[AIWatcher]", alias="EMAIL_SUBJECT_PREFIX")
    # email-mcp backend URL (optional; falls back to SMTP)
    email_mcp_url: str = Field(default="", alias="EMAIL_MCP_URL")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    # --- Calibre-mcp integration ---
    calibre_enabled: bool = Field(default=False, alias="CALIBRE_ENABLED")
    calibre_mcp_url: str = Field(default="http://localhost:10720", alias="CALIBRE_MCP_URL")
    calibre_library: str = Field(default="AI News", alias="CALIBRE_LIBRARY")

    # --- Gmail / IMAP for Alpha Signal ---
    gmail_enabled: bool = Field(default=False, alias="GMAIL_ENABLED")
    gmail_mcp_url: str = Field(default="", alias="GMAIL_MCP_URL")
    # Filter label/sender for Alpha Signal emails
    alphasignal_sender: str = Field(default="newsletter@alphasignal.ai", alias="ALPHASIGNAL_SENDER")

    # --- ArXiv integration ---
    arxiv_enabled: bool = Field(default=False, alias="ARXIV_ENABLED")
    arxiv_mcp_url: str = Field(default="http://localhost:10770", alias="ARXIV_MCP_URL")
    arxiv_categories: str = Field(default="cs.AI,cs.LG,cs.RO,cs.SD", alias="ARXIV_CATEGORIES")

    # --- VLA robotics bridge ---
    vla_mcp_enabled: bool = Field(default=True, alias="VLA_MCP_ENABLED")
    vla_mcp_url: str = Field(default="http://localhost:11024", alias="VLA_MCP_URL")

    # --- Readly-mcp integration ---
    readly_enabled: bool = Field(default=False, alias="READLY_ENABLED")
    readly_mcp_url: str = Field(default="http://localhost:10863", alias="READLY_MCP_URL")
    readly_watchlist: str = Field(
        default="",
        alias="READLY_WATCHLIST",
        description="Comma-separated magazine names for readly-mcp watchlist polling",
    )
    readly_poll_max_articles: int = Field(default=10, alias="READLY_POLL_MAX_ARTICLES")
    readly_poll_interval_hours: int = Field(default=6, alias="READLY_POLL_INTERVAL_HOURS")

    def parsed_readly_watchlist(self) -> list[str]:
        if not self.readly_watchlist.strip():
            return []
        return [part.strip() for part in self.readly_watchlist.split(",") if part.strip()]

    # --- Retention ---
    item_retention_days: int = Field(default=90, alias="ITEM_RETENTION_DAYS")

    # --- Prefab UI ---
    aiwatcher_prefab_apps: bool = Field(default=True, alias="AIWATCHER_PREFAB_APPS")

    # --- Central Docs Registry ---
    central_docs_path: str = Field(
        default="D:/Dev/repos/mcp-central-docs", alias="CENTRAL_DOCS_PATH"
    )
    interests_json_path: str = Field(default="interests.json", alias="INTERESTS_JSON_PATH")

    def resolved_interests_path(self) -> Path:
        """Repo-root interests.json when path is relative (avoids CWD drift in scheduler)."""
        raw = Path(self.interests_json_path)
        if raw.is_absolute():
            return raw
        repo_root = Path(__file__).resolve().parents[2]
        for candidate in (repo_root / raw, Path.cwd() / raw):
            if candidate.exists():
                return candidate
        return repo_root / raw


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
