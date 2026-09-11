from __future__ import annotations

import unittest
from unittest.mock import patch

from rag_enterprise_mcp.config import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_safe_and_local(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_base_url, "http://127.0.0.1:8000")
        self.assertEqual(settings.backend_timeout_seconds, 30.0)
        self.assertEqual(settings.backend_bearer_token, "")
        self.assertEqual(settings.backend_dev_login_email, "")
        self.assertEqual(settings.backend_dev_login_password, "")
        self.assertEqual(settings.server_name, "rag-enterprise-mcp")
        self.assertEqual(settings.server_version, "0.1.0")

    def test_values_are_trimmed_and_base_url_trailing_slashes_are_removed(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "RAG_BACKEND_BASE_URL": "  https://backend.example.test///  ",
                "RAG_BACKEND_BEARER_TOKEN": "  token-value  ",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_base_url, "https://backend.example.test")
        self.assertEqual(settings.backend_bearer_token, "token-value")

    def test_valid_timeout_is_parsed(self) -> None:
        with patch.dict("os.environ", {"RAG_BACKEND_TIMEOUT_SECONDS": " 12.5 "}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_timeout_seconds, 12.5)

    def test_invalid_timeout_falls_back_to_default(self) -> None:
        with patch.dict("os.environ", {"RAG_BACKEND_TIMEOUT_SECONDS": "not-a-number"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_timeout_seconds, 30.0)

    def test_timeout_is_clamped_to_one_second(self) -> None:
        with patch.dict("os.environ", {"RAG_BACKEND_TIMEOUT_SECONDS": "-3"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_timeout_seconds, 1.0)

    def test_login_and_server_identity_values_are_loaded(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "RAG_BACKEND_DEV_LOGIN_EMAIL": "reader@example.test",
                "RAG_BACKEND_DEV_LOGIN_PASSWORD": "test-password",
                "MCP_SERVER_NAME": "custom-mcp",
                "MCP_SERVER_VERSION": "2.3.4",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.backend_dev_login_email, "reader@example.test")
        self.assertEqual(settings.backend_dev_login_password, "test-password")
        self.assertEqual(settings.server_name, "custom-mcp")
        self.assertEqual(settings.server_version, "2.3.4")


if __name__ == "__main__":
    unittest.main()
