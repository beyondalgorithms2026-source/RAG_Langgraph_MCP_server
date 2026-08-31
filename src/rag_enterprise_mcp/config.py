from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    backend_base_url: str
    backend_timeout_seconds: float
    backend_bearer_token: str
    backend_dev_login_email: str
    backend_dev_login_password: str
    server_name: str
    server_version: str

    @classmethod
    def from_env(cls) -> "Settings":
        timeout_raw = _env("RAG_BACKEND_TIMEOUT_SECONDS", "30")
        try:
            timeout_value = float(timeout_raw)
        except ValueError:
            timeout_value = 30.0
        return cls(
            backend_base_url=_env("RAG_BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            backend_timeout_seconds=max(timeout_value, 1.0),
            backend_bearer_token=_env("RAG_BACKEND_BEARER_TOKEN"),
            backend_dev_login_email=_env("RAG_BACKEND_DEV_LOGIN_EMAIL"),
            backend_dev_login_password=_env("RAG_BACKEND_DEV_LOGIN_PASSWORD"),
            server_name=_env("MCP_SERVER_NAME", "rag-enterprise-mcp"),
            server_version=_env("MCP_SERVER_VERSION", "0.1.0"),
        )

