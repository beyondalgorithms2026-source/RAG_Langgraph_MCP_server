from __future__ import annotations

from typing import Any

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.schemas.backend import GetDocumentExcerptInput


GET_DOCUMENT_EXCERPT_TOOL = {
    "name": "get_document_excerpt",
    "description": "Retrieve one narrow excerpt via the backend search API, scoped to a known document or locator when possible. This does not bypass backend permissions.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "source_id": {"type": "integer"},
            "source_part_id": {"type": "integer"},
            "locator_filter": {"type": "string"},
            "metadata_filters": {"type": "object"},
            "mode": {"type": "string", "enum": ["vector", "keyword", "hybrid", "graph_hybrid", "full"], "default": "keyword"},
            "max_chars": {"type": "integer", "minimum": 100, "maximum": 4000, "default": 1200},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}


def run(client: BackendClient, arguments: dict[str, Any]) -> dict[str, Any]:
    request = GetDocumentExcerptInput.from_input(arguments)
    response = client.search(request.to_search_backend())
    results = response.get("results", [])
    if not results:
        return {
            "question": request.question,
            "matched": False,
            "excerpt": None,
            "result": None,
        }
    top_result = dict(results[0])
    snippet = str(top_result.get("snippet", ""))
    top_result["snippet"] = snippet[: request.max_chars]
    return {
        "question": request.question,
        "matched": True,
        "excerpt": top_result.get("snippet"),
        "result": top_result,
    }

