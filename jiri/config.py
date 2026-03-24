"""Pydantic settings for Jiri."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_workspaces_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "workspaces"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    workspaces_dir: Path = Field(
        default_factory=_default_workspaces_dir,
        description="Directory for persistent git clones and checkpoints.",
    )
    webhook_secret: str = Field(
        default="",
        description="If set, X-Hub-Signature-256 must validate (GitHub webhook secret).",
    )
    event_allowlist: str = Field(
        default="",
        description="Comma-separated GitHub event names; empty = all supported.",
    )
    repo_allowlist: str = Field(
        default="",
        description="Comma-separated owner/repo; empty = any repository.",
    )
    trigger_keywords: str = Field(
        default="/test,@jiri",
        description="Comma-separated substrings; issue_comment must contain one to trigger.",
    )

    github_token: str = Field(default="", description="GitHub PAT for issues/comments API.")
    github_default_repo: str = Field(
        default="",
        description="Optional default owner/repo when payload lacks repository (e.g. owner/repo).",
    )

    test_commands: str = Field(
        default="",
        description="Comma-separated commands to try in order (e.g. pytest,npm test). Empty = auto-detect.",
    )
    test_timeout: int = Field(default=600, ge=30, le=7200)
    webhook_dry_run: bool = Field(
        default=False,
        description="If true, skip git clone/pull and fake test output.",
    )

    ui_test_enabled: bool = Field(default=False)
    ui_test_base_url: str = Field(default="http://127.0.0.1:3000")
    ui_test_timeout_ms: int = Field(default=30_000, ge=1000, le=300_000)
    ui_test_paths: str = Field(
        default="/",
        description="Comma-separated URL paths to smoke-test (relative to base URL).",
    )

    openai_api_key: str = Field(default="", description="OpenAI API key for planner/analyzer.")
    openai_model: str = Field(default="gpt-4o", description="Model for LangChain agents.")

    jannus_api_url: str = Field(
        default="",
        description="Base URL of Jannus (e.g. http://jannus-host:8765), no trailing slash.",
    )
    jannus_api_secret: str = Field(
        default="",
        description="Optional shared secret for X-Jiri-Secret header to Jannus.",
    )
    jiri_public_base_url: str = Field(
        default="",
        description="Public URL of this Jiri instance for callbacks (e.g. https://jiri.example.com).",
    )
    jiri_inbound_secret: str = Field(
        default="",
        description="Optional secret for inbound /api/test-request and /api/negotiate (X-Jiri-Secret).",
    )

    negotiation_max_rounds: int = Field(default=3, ge=1, le=10)

    jiri_telegram_bot_token: str = Field(default="", description="Telegram bot token for Jiri notifications.")
    jiri_telegram_chat_id: str = Field(default="", description="Telegram chat id for Jiri.")

    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="jiri")

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8766, ge=1, le=65535)

    def parsed_event_allowlist(self) -> set[str]:
        if not self.event_allowlist.strip():
            return set()
        return {x.strip().lower() for x in self.event_allowlist.split(",") if x.strip()}

    def parsed_repo_allowlist(self) -> set[str]:
        if not self.repo_allowlist.strip():
            return set()
        return {x.strip().lower() for x in self.repo_allowlist.split(",") if x.strip()}

    def parsed_trigger_keywords(self) -> list[str]:
        if not self.trigger_keywords.strip():
            return []
        return [x.strip() for x in self.trigger_keywords.split(",") if x.strip()]

    def parsed_test_commands(self) -> list[str]:
        if not self.test_commands.strip():
            return []
        return [x.strip() for x in self.test_commands.split(",") if x.strip()]

    def parsed_ui_paths(self) -> list[str]:
        if not self.ui_test_paths.strip():
            return ["/"]
        return [p.strip() or "/" for p in self.ui_test_paths.split(",") if p.strip() or p == "/"]

    @property
    def checkpoint_db_path(self) -> Path:
        return self.workspaces_dir / ".jiri_state.db"

    @property
    def registry_path(self) -> Path:
        return self.workspaces_dir / "registry.json"


_settings: Settings | None = None


def load_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
