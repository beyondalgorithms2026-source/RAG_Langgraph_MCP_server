from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any
from urllib import error, parse, request

from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError


class BackendClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cookie_jar = CookieJar()
        self.opener = request.build_opener(request.HTTPCookieProcessor(self.cookie_jar))
        self._authenticated = False

    def ask(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/ask", payload)

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json("/search", payload)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", path, payload)

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None, *, retry_on_auth: bool = True) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.settings.backend_bearer_token:
            headers["Authorization"] = "Bearer " + self.settings.backend_bearer_token
        req = request.Request(self.settings.backend_base_url + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.settings.backend_timeout_seconds) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except error.HTTPError as exc:
            payload_data = self._decode_error_payload(exc)
            if exc.code == 401 and retry_on_auth and self._can_attempt_dev_login():
                self._login_local_dev()
                return self._request_json(method, path, payload, retry_on_auth=False)
            raise BackendError(self._error_message(exc.code, payload_data), status_code=exc.code, payload=payload_data) from exc
        except error.URLError as exc:
            raise BackendError(f"Failed to reach backend at {self.settings.backend_base_url}: {exc.reason}") from exc

    def _can_attempt_dev_login(self) -> bool:
        return (
            not self.settings.backend_bearer_token
            and not self._authenticated
            and bool(self.settings.backend_dev_login_email)
            and bool(self.settings.backend_dev_login_password)
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

