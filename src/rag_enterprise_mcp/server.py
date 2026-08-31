from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError, ValidationError
from rag_enterprise_mcp.tools import TOOLS
from rag_enterprise_mcp.tools import ask_grounded, get_document_excerpt, search_documents


ToolHandler = Callable[[BackendClient, dict[str, Any]], dict[str, Any]]
SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
    "2024-10-07",
)


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "ask_grounded": ask_grounded.run,
    "search_documents": search_documents.run,
    "get_document_excerpt": get_document_excerpt.run,
}


class StdioJsonRpcServer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = BackendClient(settings)

    def serve_forever(self) -> None:
        self._log_stderr("server.start")
        while True:
            message = self._read_message()
            if message is None:
                self._log_stderr("server.stop eof")
                return
            self._log_stderr("server.recv " + self._safe_json(message))
            if "id" not in message:
                self._dispatch_notification(message)
                continue
            response = self._dispatch(message)
            self._log_stderr("server.send " + self._safe_json(response))
            self._write_message(response)

    def _dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        try:
            if method == "initialize":
                requested_version = str(params.get("protocolVersion") or "").strip()
                negotiated_version = self._negotiate_protocol_version(requested_version)
                return self._success(
                    request_id,
                    {
                        "protocolVersion": negotiated_version,
                        "serverInfo": {
                            "name": self.settings.server_name,
                            "version": self.settings.server_version,
                        },
                        "capabilities": {
                            "tools": {
                                "listChanged": False,
                            },
                        },
                        "instructions": "Use these tools to access the local enterprise RAG backend over HTTP. The server does not bypass backend ACLs, retrieval rules, or auth behavior.",
                    },
                )
            if method == "tools/list":
                return self._success(request_id, {"tools": TOOLS})
            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if name not in TOOL_HANDLERS:
                    raise ValidationError(f"Unknown tool: {name}")
                result = TOOL_HANDLERS[name](self.client, arguments)
                return self._success(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2, sort_keys=True),
                            }
                        ],
                        "structuredContent": result,
                        "isError": False,
                    },
                )
            raise ValidationError(f"Unsupported method: {method}")
        except ValidationError as exc:
            return self._tool_error(request_id, str(exc), code=-32602)
        except BackendError as exc:
            detail = {
                "message": exc.message,
                "status_code": exc.status_code,
                "payload": exc.payload,
            }
            return self._success(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(detail, indent=2, sort_keys=True)}],
                    "structuredContent": detail,
                    "isError": True,
                },
            )
        except Exception as exc:  # pragma: no cover
            detail = {
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
            return self._tool_error(request_id, json.dumps(detail, indent=2, sort_keys=True), code=-32603)

    @staticmethod
    def _success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _negotiate_protocol_version(requested_version: str) -> str:
        if requested_version in SUPPORTED_PROTOCOL_VERSIONS:
            return requested_version
        return SUPPORTED_PROTOCOL_VERSIONS[0]

    def _dispatch_notification(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method in {"notifications/initialized", "notifications/cancelled"}:
            return
        self._log_stderr(f"server.ignored_notification {method}")

    @staticmethod
    def _tool_error(request_id: Any, message: str, *, code: int) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _read_message() -> dict[str, Any] | None:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        payload = line.decode("utf-8").strip()
        if not payload:
            return None
        return json.loads(payload)

    @staticmethod
    def _write_message(payload: dict[str, Any]) -> None:
        raw = (json.dumps(payload) + "\n").encode("utf-8")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()

    @staticmethod
    def _safe_json(payload: dict[str, Any]) -> str:
        try:
            return json.dumps(payload, sort_keys=True)
        except Exception:
            return repr(payload)

    @staticmethod
    def _log_stderr(message: str) -> None:
        print(message, file=sys.stderr, flush=True)


def main() -> None:
    settings = Settings.from_env()
    server = StdioJsonRpcServer(settings)
    server.serve_forever()


if __name__ == "__main__":
    main()
