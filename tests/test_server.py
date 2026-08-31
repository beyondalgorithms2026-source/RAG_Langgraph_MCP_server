from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from rag_enterprise_mcp.config import Settings
from rag_enterprise_mcp.server import StdioJsonRpcServer


class _BufferWrapper:
    def __init__(self, buffer: io.BytesIO):
        self.buffer = buffer


class ServerTests(unittest.TestCase):
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
        with patch.object(server.client, "ask", return_value={"answer": "A", "citations": [], "used_chunks_count": 1, "latency_ms": 10, "mode": "hybrid"}):
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

        with patch("sys.stdin", _BufferWrapper(stdin_buffer)), patch("sys.stdout", _BufferWrapper(stdout_buffer)):
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


if __name__ == "__main__":
    unittest.main()
