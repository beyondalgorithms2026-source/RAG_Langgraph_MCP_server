from __future__ import annotations

import io
import json
import unittest
from urllib.error import HTTPError

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError


class _MockResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "_MockResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _MockOpener:
    def __init__(self) -> None:
        self.login_calls = 0
        self.ask_calls = 0

    def open(self, req, timeout=0):  # noqa: ANN001
        if req.full_url.endswith("/auth/local-dev-login"):
            self.login_calls += 1
            return _MockResponse({"user": {"email": "test-user@example.com"}})
        if req.full_url.endswith("/ask"):
            self.ask_calls += 1
            if self.ask_calls == 1:
                raise HTTPError(
                    req.full_url,
                    401,
                    "Unauthorized",
                    hdrs=None,
                    fp=io.BytesIO(
                        b'{"detail":{"error":"authentication_required","message":"Authentication is required for this endpoint."}}'
                    ),
                )
            return _MockResponse(
                {
                    "answer": "Grounded answer",
                    "citations": [],
                    "used_chunks_count": 1,
                    "latency_ms": 12,
                    "mode": "hybrid",
                }
            )
        raise AssertionError(f"Unexpected URL {req.full_url}")


class BackendClientTests(unittest.TestCase):
    def test_client_retries_after_local_dev_login(self) -> None:
        settings = Settings(
            backend_base_url="http://127.0.0.1:8000",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="test-user@example.com",
            backend_dev_login_password="password123",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)
        opener = _MockOpener()
        client.opener = opener
        result = client.ask({"question": "What is the answer?"})
        self.assertEqual(result["answer"], "Grounded answer")
        self.assertEqual(opener.login_calls, 1)
        self.assertEqual(opener.ask_calls, 2)

    def test_client_surfaces_backend_error(self) -> None:
        settings = Settings(
            backend_base_url="http://127.0.0.1:8000",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)
        opener = _MockOpener()
        client.opener = opener
        with self.assertRaises(BackendError) as ctx:
            client.ask({"question": "What is the answer?"})
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Authentication is required", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
