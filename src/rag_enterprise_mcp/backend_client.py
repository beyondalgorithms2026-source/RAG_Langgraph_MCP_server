from __future__ import annotations

import json
import time
from http.cookiejar import CookieJar
from typing import Any
from urllib import error, request

from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError


class BackendClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cookie_jar = CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookie_jar))
        self._authenticated = False
        self._backend_ready = False
        self._sleep = time.sleep
        self._monotonic = time.monotonic

    def ask(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/ask", payload)

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/search", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_backend_ready()
        return self._request_json("POST", path, payload)

    def _ensure_backend_ready(self) -> None:
        """Wait for a sleeping backend before sending a potentially costly POST."""
        if self._backend_ready:
            return

        deadline = self._monotonic() + self.settings.backend_timeout_seconds
        delay_seconds = 1.0
        last_error = "Backend is not ready."
        while True:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise BackendError(last_error)

            req = request.Request(
                self.settings.backend_base_url + "/health",
                headers={"Accept": "application/json"},
                method="GET",
            )
            try:
                with self.opener.open(req, timeout=remaining) as response:
                    content = response.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    if not self._is_wake_response(content):
                        raise BackendError(
                            "Backend health check returned a non-JSON response."
                        ) from None
                    last_error = "Backend did not finish waking before the configured timeout."
                else:
                    if isinstance(payload, dict) and payload.get("status") == "ok":
                        self._backend_ready = True
                        return
                    raise BackendError(
                        "Backend health check did not report status 'ok'.", payload=payload
                    )
            except error.HTTPError as exc:
                if exc.code not in {502, 503, 504}:
                    payload = self._decode_error_payload(exc)
                    raise BackendError(
                        self._error_message(exc.code, payload),
                        status_code=exc.code,
                        payload=payload,
                    ) from exc
                last_error = f"Backend remained unavailable while waking (HTTP {exc.code})."
            except error.URLError as exc:
                last_error = f"Failed to reach backend while waiting for readiness: {exc.reason}"
            except TimeoutError:
                last_error = "Timed out while waiting for the backend to finish waking."

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise BackendError(last_error)
            self._sleep(min(delay_seconds, remaining))
            delay_seconds = min(delay_seconds * 2, 10.0)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        retry_on_auth: bool = True,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.settings.backend_bearer_token:
            headers["Authorization"] = "Bearer " + self.settings.backend_bearer_token
        req = request.Request(
            self.settings.backend_base_url + path, data=body, headers=headers, method=method
        )
        try:
            with self.opener.open(req, timeout=self.settings.backend_timeout_seconds) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except error.HTTPError as exc:
            payload_data = self._decode_error_payload(exc)
            if exc.code == 401 and retry_on_auth and self._can_attempt_dev_login():
                self._login_local_dev()
                return self._request_json(method, path, payload, retry_on_auth=False)
            raise BackendError(
                self._error_message(exc.code, payload_data),
                status_code=exc.code,
                payload=payload_data,
            ) from exc
        except error.URLError as exc:
            raise BackendError(
                f"Failed to reach backend at {self.settings.backend_base_url}: {exc.reason}"
            ) from exc

    def _can_attempt_dev_login(self) -> bool:
        return (
            not self.settings.backend_bearer_token
            and not self._authenticated
            and bool(self.settings.backend_dev_login_email)
            and bool(self.settings.backend_dev_login_password)
        )

    @staticmethod
    def _is_wake_response(content: str) -> bool:
        normalized = content.casefold()
        return (
            "service waking up" in normalized
            or "application loading" in normalized
            or ("render" in normalized and "<!doctype html" in normalized)
        )

    def _login_local_dev(self) -> None:
        body = {
            "email": self.settings.backend_dev_login_email,
            "password": self.settings.backend_dev_login_password,
        }
        self._request_json("POST", "/auth/local-dev-login", body, retry_on_auth=False)
        self._authenticated = True

    @staticmethod
    def _decode_error_payload(exc: error.HTTPError) -> object | None:
        raw = exc.read().decode("utf-8", errors="replace")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    @staticmethod
    def _error_message(status_code: int, payload: object | None) -> str:
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("error")
                if message:
                    return f"Backend returned {status_code}: {message}"
            message = payload.get("message") or payload.get("error")
            if message:
                return f"Backend returned {status_code}: {message}"
        if isinstance(payload, str) and payload.strip():
            return f"Backend returned {status_code}: {payload.strip()}"
        return f"Backend returned HTTP {status_code}."
