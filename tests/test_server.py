from __future__ import annotations

import io
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.exceptions import BackendError
from rag_enterprise_mcp.server import TOOL_HANDLERS, StdioJsonRpcServer


class _BufferWrapper:
    def __init__(self, buffer: io.BytesIO):
        self.buffer = buffer


class ServerTests(unittest.TestCase):
    @staticmethod
    def _server() -> StdioJsonRpcServer:
        return StdioJsonRpcServer(
            Settings(
                backend_base_url="http://127.0.0.1:8000",
                backend_timeout_seconds=5.0,
                backend_bearer_token="",
                backend_dev_login_email="",
                backend_dev_login_password="",
                server_name="test",
                server_version="0.1.0",
            )
        )

    def test_tools_call_returns_structured_result(self) -> None:
        settings = Settings(
            backend_base_url="http://127.0.0.1:8000",
            backend_timeout_seconds=5.0,
            backend_bearer_token="",
            backend_dev_login_email="",
            backend_dev_login_password="",
            server_name="test",
            server_version="0.1.0",
        )
        server = StdioJsonRpcServer(settings)
        with patch.object(
            server.client,
            "ask",
            return_value={
                "answer": "A",
                "citations": [],
                "used_chunks_count": 1,
                "latency_ms": 10,
                "mode": "hybrid",
            },
        ):
            response = server._dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "ask_grounded", "arguments": {"question": "Q"}},
                }
            )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["answer"], "A")

    def test_initialize_round_trip(self) -> None:
        payload = {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}}
        raw = (json.dumps(payload) + "\n").encode("utf-8")
        stdin_buffer = io.BytesIO(raw)
        stdout_buffer = io.BytesIO()

        with (
            patch("sys.stdin", _BufferWrapper(stdin_buffer)),
            patch("sys.stdout", _BufferWrapper(stdout_buffer)),
        ):
            settings = Settings(
                backend_base_url="http://127.0.0.1:8000",
                backend_timeout_seconds=5.0,
                backend_bearer_token="",
                backend_dev_login_email="",
                backend_dev_login_password="",
                server_name="test",
                server_version="0.1.0",
            )
            server = StdioJsonRpcServer(settings)
            message = server._read_message()
            server._write_message(server._dispatch(message))

        output = stdout_buffer.getvalue()
        response = json.loads(output.decode("utf-8").strip())
        self.assertEqual(response["id"], 7)
        self.assertEqual(response["result"]["serverInfo"]["name"], "test")

    def test_tools_list_returns_registered_schemas(self) -> None:
        response = self._server()._dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

        tools = response["result"]["tools"]
        self.assertEqual(
            [tool["name"] for tool in tools],
            ["ask_grounded", "search_documents", "get_document_excerpt"],
        )
        self.assertTrue(all("inputSchema" in tool for tool in tools))

    def test_unknown_method_returns_invalid_params_error(self) -> None:
        response = self._server()._dispatch(
            {"jsonrpc": "2.0", "id": "request-3", "method": "prompts/list"}
        )

        self.assertEqual(response["id"], "request-3")
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("Unsupported method", response["error"]["message"])

    def test_unknown_tool_and_missing_arguments_are_validation_errors(self) -> None:
        server = self._server()
        unknown = server._dispatch(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "not-a-tool", "arguments": {}},
            }
        )
        missing = server._dispatch(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "ask_grounded"},
            }
        )

        self.assertEqual(unknown["error"]["code"], -32602)
        self.assertIn("Unknown tool", unknown["error"]["message"])
        self.assertEqual(missing["error"]["code"], -32602)
        self.assertIn("question is required", missing["error"]["message"])

    def test_backend_error_is_returned_as_structured_tool_failure(self) -> None:
        server = self._server()
        failure = BackendError("Backend unavailable", status_code=503, payload={"retry": True})
        with patch.object(server.client, "ask", side_effect=failure):
            response = server._dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "ask_grounded", "arguments": {"question": "Q"}},
                }
            )

        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["status_code"], 503)
        self.assertEqual(result["structuredContent"]["payload"], {"retry": True})

    def test_malformed_json_input_is_rejected(self) -> None:
        with (
            patch("sys.stdin", _BufferWrapper(io.BytesIO(b"{not-json}\n"))),
            self.assertRaises(json.JSONDecodeError),
        ):
            self._server()._read_message()

    def test_concurrent_tool_dispatch_keeps_request_results_separate(self) -> None:
        server = self._server()
        barrier = threading.Barrier(2)

        def handler(client, arguments):
            barrier.wait(timeout=2)
            return {"question": arguments["question"]}

        messages = [
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": "ask_grounded",
                    "arguments": {"question": f"Q{request_id}"},
                },
            }
            for request_id in (10, 11)
        ]

        with (
            patch.dict(TOOL_HANDLERS, {"ask_grounded": handler}),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            responses = list(pool.map(server._dispatch, messages))

        self.assertEqual(
            [(item["id"], item["result"]["structuredContent"]["question"]) for item in responses],
            [(10, "Q10"), (11, "Q11")],
        )


if __name__ == "__main__":
    unittest.main()
