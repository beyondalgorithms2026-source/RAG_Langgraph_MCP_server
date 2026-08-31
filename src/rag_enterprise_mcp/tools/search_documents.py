from __future__ import annotations

from typing import Any

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.schemas.backend import SearchDocumentsInput


SEARCH_DOCUMENTS_TOOL = {
    "name": "search_documents",
    "description": "Search the enterprise RAG backend for relevant document chunks. Results stay subject to backend retrieval policy and ACL trimming.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8},
            "mode": {"type": "string", "enum": ["vector", "keyword", "hybrid", "graph_hybrid", "full"]},
            "filters": {"type": "object"},
            "deep_research": {"type": "boolean", "default": False},
            "custom_query": {"type": "string"},
            "anchor_terms": {"type": "array", "items": {"type": "string"}},
            "exact_phrase_bias": {"type": "string"},
            "expand_neighbors": {"type": "boolean", "default": False},
            "force_rare_keyword_scan": {"type": "boolean", "default": False},
            "debug": {"type": "boolean", "default": False},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}


def run(client: BackendClient, arguments: dict[str, Any]) -> dict[str, Any]:
    request = SearchDocumentsInput.from_input(arguments)
    response = client.search(request.to_backend())
    return {
        "question": request.question,
        "mode": response.get("mode"),
        "latency_ms": response.get("latency_ms", 0),
        "results": response.get("results", []),
        "debug_info": response.get("debug_info"),
    }

