from __future__ import annotations

import io
import json
import unittest
from urllib import request
from urllib.error import HTTPError, URLError

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError


class _MockResponse:
    def __init__(self, payload: dict | None = None, *, raw: bytes | None = None):
        self.payload = payload
        self.raw = raw

    def read(self) -> bytes:
        return self.raw if self.raw is not None else json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> _MockResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _MockOpener:
    def __init__(self) -> None:
        self.login_calls = 0
        self.ask_calls = 0
        self.health_calls = 0

    def open(self, req, timeout=0):
        if req.full_url.endswith("/health"):
            self.health_calls += 1
            return _MockResponse({"status": "ok"})
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
    def test_client_opener_uses_the_persistent_cookie_jar(self) -> None:
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

        cookie_processors = [
            handler
            for handler in client.opener.handlers
            if isinstance(handler, request.HTTPCookieProcessor)
        ]
        self.assertEqual(len(cookie_processors), 1)
        self.assertIs(cookie_processors[0].cookiejar, client.cookie_jar)

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
        self.assertEqual(opener.health_calls, 1)

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

    def test_client_waits_through_render_wake_page_before_posting_once(self) -> None:
        settings = Settings(
            backend_base_url="https://example.onrender.com",
            backend_timeout_seconds=120.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class WakeThenReadyOpener(_MockOpener):
            def open(self, req, timeout=0):
                if req.full_url.endswith("/health"):
                    self.health_calls += 1
                    if self.health_calls < 3:
                        return _MockResponse(
                            raw=b"<!doctype html><p>SERVICE WAKING UP</p><p>APPLICATION LOADING</p>"
                        )
                    return _MockResponse({"status": "ok"})
                if req.full_url.endswith("/ask"):
                    self.ask_calls += 1
                    return _MockResponse({"answer": "Grounded answer", "citations": []})
                raise AssertionError(f"Unexpected URL {req.full_url}")

        opener = WakeThenReadyOpener()
        client.opener = opener
        sleeps: list[float] = []
        client._sleep = sleeps.append
        result = client.ask({"question": "What is the answer?"})

        self.assertEqual(result["answer"], "Grounded answer")
        self.assertEqual(opener.health_calls, 3)
        self.assertEqual(opener.ask_calls, 1)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_client_does_not_retry_unexpected_health_html(self) -> None:
        settings = Settings(
            backend_base_url="https://backend.example.com",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class UnexpectedHtmlOpener(_MockOpener):
            def open(self, req, timeout=0):
                self.health_calls += 1
                return _MockResponse(raw=b"<html><body>Proxy configuration error</body></html>")

        opener = UnexpectedHtmlOpener()
        client.opener = opener
        with self.assertRaisesRegex(BackendError, "non-JSON"):
            client.ask({"question": "What is the answer?"})
        self.assertEqual(opener.health_calls, 1)
        self.assertEqual(opener.ask_calls, 0)

    def test_client_waits_through_transient_health_error_without_reposting(self) -> None:
        settings = Settings(
            backend_base_url="https://example.onrender.com",
            backend_timeout_seconds=120.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class UnavailableThenReadyOpener(_MockOpener):
            def open(self, req, timeout=0):
                if req.full_url.endswith("/health"):
                    self.health_calls += 1
                    if self.health_calls == 1:
                        raise HTTPError(
                            req.full_url, 503, "Unavailable", hdrs=None, fp=io.BytesIO(b"")
                        )
                    return _MockResponse({"status": "ok"})
                if req.full_url.endswith("/ask"):
                    self.ask_calls += 1
                    return _MockResponse({"answer": "Grounded answer", "citations": []})
                raise AssertionError(f"Unexpected URL {req.full_url}")

        opener = UnavailableThenReadyOpener()
        client.opener = opener
        client._sleep = lambda _: None
        client.ask({"question": "What is the answer?"})
        self.assertEqual(opener.health_calls, 2)
        self.assertEqual(opener.ask_calls, 1)

    def test_client_stops_wake_checks_at_configured_deadline(self) -> None:
        settings = Settings(
            backend_base_url="https://example.onrender.com",
            backend_timeout_seconds=3.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class AlwaysWakingOpener(_MockOpener):
            def open(self, req, timeout=0):
                self.health_calls += 1
                return _MockResponse(raw=b"<!doctype html><p>APPLICATION LOADING</p>")

        opener = AlwaysWakingOpener()
        client.opener = opener
        clock = [0.0]
        client._monotonic = lambda: clock[0]
        client._sleep = lambda seconds: clock.__setitem__(0, clock[0] + seconds)

        with self.assertRaisesRegex(BackendError, "finish waking"):
            client.ask({"question": "What is the answer?"})
        self.assertEqual(opener.health_calls, 2)
        self.assertEqual(opener.ask_calls, 0)

    def test_client_normalizes_socket_timeout_without_posting(self) -> None:
        settings = Settings(
            backend_base_url="https://example.onrender.com",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class TimedOutOpener(_MockOpener):
            def open(self, req, timeout=0):
                self.health_calls += 1
                raise TimeoutError("socket timed out")

        opener = TimedOutOpener()
        client.opener = opener
        clock = [0.0]
        client._monotonic = lambda: clock[0]
        client._sleep = lambda seconds: clock.__setitem__(0, clock[0] + seconds)

        with self.assertRaisesRegex(BackendError, "Timed out"):
            client.ask({"question": "What is the answer?"})
        self.assertGreater(opener.health_calls, 1)
        self.assertEqual(opener.ask_calls, 0)

    def test_readiness_backoff_doubles_and_caps_at_ten_seconds(self) -> None:
        settings = Settings(
            backend_base_url="https://example.onrender.com",
            backend_timeout_seconds=37.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class AlwaysWakingOpener(_MockOpener):
            def open(self, req, timeout=0):
                self.health_calls += 1
                return _MockResponse(raw=b"<p>service waking up</p>")

        opener = AlwaysWakingOpener()
        client.opener = opener
        clock = [0.0]
        sleeps: list[float] = []
        client._monotonic = lambda: clock[0]

        def advance(seconds: float) -> None:
            sleeps.append(seconds)
            clock[0] += seconds

        client._sleep = advance
        with self.assertRaises(BackendError):
            client.ask({"question": "Q"})

        self.assertEqual(sleeps, [1.0, 2.0, 4.0, 8.0, 10.0, 10.0, 2.0])
        self.assertEqual(opener.health_calls, 7)

    def test_successful_readiness_check_is_cached_across_requests(self) -> None:
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

        class ReadyOpener(_MockOpener):
            def open(self, req, timeout=0):
                if req.full_url.endswith("/health"):
                    self.health_calls += 1
                    return _MockResponse({"status": "ok"})
                if req.full_url.endswith("/ask"):
                    self.ask_calls += 1
                    return _MockResponse({"answer": "Grounded answer"})
                raise AssertionError(f"Unexpected URL {req.full_url}")

        opener = ReadyOpener()
        client.opener = opener

        client.ask({"question": "first"})
        client.ask({"question": "second"})

        self.assertEqual(opener.health_calls, 1)
        self.assertEqual(opener.ask_calls, 2)

    def test_authentication_retry_happens_at_most_once(self) -> None:
        settings = Settings(
            backend_base_url="http://127.0.0.1:8000",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="reader@example.test",
            backend_dev_login_password="password",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class AlwaysUnauthorizedOpener(_MockOpener):
            def open(self, req, timeout=0):
                if req.full_url.endswith("/health"):
                    self.health_calls += 1
                    return _MockResponse({"status": "ok"})
                if req.full_url.endswith("/auth/local-dev-login"):
                    self.login_calls += 1
                    return _MockResponse({"user": {"email": "reader@example.test"}})
                if req.full_url.endswith("/ask"):
                    self.ask_calls += 1
                    raise HTTPError(
                        req.full_url, 401, "Unauthorized", hdrs=None, fp=io.BytesIO(b"")
                    )
                raise AssertionError(f"Unexpected URL {req.full_url}")

        opener = AlwaysUnauthorizedOpener()
        client.opener = opener
        with self.assertRaises(BackendError) as ctx:
            client.ask({"question": "Q"})

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(opener.login_calls, 1)
        self.assertEqual(opener.ask_calls, 2)

    def test_bearer_token_is_sent_and_disables_dev_login(self) -> None:
        settings = Settings(
            backend_base_url="https://backend.example.test",
            backend_timeout_seconds=5.0,
            backend_bearer_token="test-bearer",
            backend_dev_login_email="reader@example.test",
            backend_dev_login_password="password",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)
        client._backend_ready = True
        seen_headers: list[str | None] = []

        class RecordingOpener(_MockOpener):
            def open(self, req, timeout=0):
                seen_headers.append(req.get_header("Authorization"))
                return _MockResponse({"answer": "A"})

        client.opener = RecordingOpener()
        client.ask({"question": "Q"})

        self.assertEqual(seen_headers, ["Bearer test-bearer"])
        self.assertFalse(client._can_attempt_dev_login())

    def test_post_url_error_is_normalized(self) -> None:
        settings = Settings(
            backend_base_url="https://backend.example.test",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)
        client._backend_ready = True

        class UnreachableOpener(_MockOpener):
            def open(self, req, timeout=0):
                raise URLError("connection refused")

        client.opener = UnreachableOpener()
        with self.assertRaisesRegex(BackendError, "connection refused"):
            client.search({"question": "Q"})

    def test_non_transient_health_error_preserves_nested_detail(self) -> None:
        settings = Settings(
            backend_base_url="https://backend.example.test",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        client = BackendClient(settings)

        class ForbiddenHealthOpener(_MockOpener):
            def open(self, req, timeout=0):
                raise HTTPError(
                    req.full_url,
                    403,
                    "Forbidden",
                    hdrs=None,
                    fp=io.BytesIO(b'{"detail":{"message":"Access denied"}}'),
                )

        client.opener = ForbiddenHealthOpener()
        with self.assertRaisesRegex(BackendError, "Access denied") as ctx:
            client.ask({"question": "Q"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_wake_response_detection_is_narrow_and_case_insensitive(self) -> None:
        self.assertTrue(BackendClient._is_wake_response("SERVICE WAKING UP"))
        self.assertTrue(BackendClient._is_wake_response("<!doctype html><title>Render</title>"))
        self.assertFalse(BackendClient._is_wake_response("<html>generic proxy failure</html>"))


if __name__ == "__main__":
    unittest.main()
