"""
Settings — pydantic-settings with .env support.
All config lives here; never scatter os.getenv calls.
"""

from __future__ import annotations

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
    server_version: str = "0.1.0"
    backend_port: int = Field(default=10946, alias="BACKEND_PORT")
    frontend_port: int = Field(default=10947, alias="FRONTEND_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---
    db_path: str = Field(default="data/aiwatcher.db", alias="DB_PATH")

    # --- Feed polling ---
    feed_poll_interval_minutes: int = Field(default=30, alias="FEED_POLL_INTERVAL_MINUTES")
    max_items_per_feed: int = Field(default=50, alias="MAX_ITEMS_PER_FEED")

    # --- Claude distillation ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    distillation_model: str = Field(
        default="claude-sonnet-4-20250514", alias="DISTILLATION_MODEL"
    )
    distillation_interval_hours: int = Field(
        default=6, alias="DISTILLATION_INTERVAL_HOURS"
    )

    # --- Alert thresholds ---
    # Score 0-10; items >= this wake Sandra up
    alert_threshold: float = Field(default=8.5, alias="ALERT_THRESHOLD")
    alert_hour_utc: int = Field(default=4, alias="ALERT_HOUR_UTC")  # 4 UTC = 5am Vienna
    alert_minute_utc: int = Field(default=55, alias="ALERT_MINUTE_UTC")

    # --- Speechops integration ---
    speechops_backend_url: str = Field(
        default="http://localhost:10946", alias="SPEECHOPS_BACKEND_URL"
    )
    # Direct HTTP to speechops server (separate port, fleet convention)
    speechops_http_url: str = Field(
        default="http://localhost:10895", alias="SPEECHOPS_HTTP_URL"
    )

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
    email_subject_prefix: str = Field(
        default="[AIWatcher]", alias="EMAIL_SUBJECT_PREFIX"
    )
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
    alphasignal_sender: str = Field(
        default="newsletter@alphasignal.ai", alias="ALPHASIGNAL_SENDER"
    )

    # --- Prefab UI ---
    aiwatcher_prefab_apps: bool = Field(default=True, alias="AIWATCHER_PREFAB_APPS")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
