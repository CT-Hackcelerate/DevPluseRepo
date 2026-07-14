"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional at runtime
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Config:
    """Runtime configuration for the optimizer and all integrations."""

    # Claude
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: _env("TOKENOPT_MODEL", "claude-opus-4-8"))
    summary_model: str = field(
        default_factory=lambda: _env("TOKENOPT_SUMMARY_MODEL", "claude-haiku-4-5")
    )
    cache_dir: str = field(default_factory=lambda: _env("TOKENOPT_CACHE_DIR", ".tokenopt_cache"))

    # Optional local model (Ollama) for abstractive summarization with no cloud
    # tokens. Set TOKENOPT_LOCAL_MODEL to a pulled model name (e.g. "llama3.2").
    local_model: str = field(default_factory=lambda: _env("TOKENOPT_LOCAL_MODEL"))
    local_model_url: str = field(
        default_factory=lambda: _env("TOKENOPT_LOCAL_MODEL_URL", "http://localhost:11434")
    )

    # JIRA
    jira_base_url: str = field(default_factory=lambda: _env("JIRA_BASE_URL"))
    jira_email: str = field(default_factory=lambda: _env("JIRA_EMAIL"))
    jira_api_token: str = field(default_factory=lambda: _env("JIRA_API_TOKEN"))

    # GitHub
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN"))
    github_api_url: str = field(
        default_factory=lambda: _env("GITHUB_API_URL", "https://api.github.com")
    )

    # Azure DevOps
    azdo_org_url: str = field(default_factory=lambda: _env("AZDO_ORG_URL"))
    azdo_project: str = field(default_factory=lambda: _env("AZDO_PROJECT"))
    azdo_pat: str = field(default_factory=lambda: _env("AZDO_PAT"))

    # GitLab
    gitlab_base_url: str = field(
        default_factory=lambda: _env("GITLAB_BASE_URL", "https://gitlab.com")
    )
    gitlab_token: str = field(default_factory=lambda: _env("GITLAB_TOKEN"))

    # Jenkins
    jenkins_base_url: str = field(default_factory=lambda: _env("JENKINS_BASE_URL"))
    jenkins_user: str = field(default_factory=lambda: _env("JENKINS_USER"))
    jenkins_api_token: str = field(default_factory=lambda: _env("JENKINS_API_TOKEN"))

    def require(self, *attrs: str) -> None:
        """Raise a clear error if any required config values are missing."""
        missing = [a for a in attrs if not getattr(self, a, "")]
        if missing:
            raise RuntimeError(
                "Missing required configuration: "
                + ", ".join(missing)
                + ". Set them in your environment or .env file (see .env.example)."
            )
