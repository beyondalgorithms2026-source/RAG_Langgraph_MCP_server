from __future__ import annotations

from typing import Any

from rag_enterprise_mcp.backend_client import BackendClient
from rag_enterprise_mcp.schemas.backend import AskGroundedInput


ASK_GROUNDED_TOOL = {
    "name": "ask_grounded",
    "description": "Ask the enterprise RAG backend for a grounded answer with citations. Uses backend retrieval, ACL trimming, and answer generation without bypassing them.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The user question to answer."},
            "k_chunks": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
            "mode": {"type": "string", "enum": ["vector", "keyword", "hybrid", "graph_hybrid", "full"]},
            "filters": {"type": "object"},
            "deep_research": {"type": "boolean", "default": False},
            "custom_query": {"type": "string"},
            "anchor_terms": {"type": "array", "items": {"type": "string"}},
            "exact_phrase_bias": {"type": "string"},
            "expand_neighbors": {"type": "boolean", "default": False},
            "dry_run": {"type": "boolean", "default": False},
            "force_rare_keyword_scan": {"type": "boolean", "default": False},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}


def run(client: BackendClient, arguments: dict[str, Any]) -> dict[str, Any]:
    request = AskGroundedInput.from_input(arguments)
    response = client.ask(request.to_backend())
    return {
        "question": request.question,
        "answer": response.get("answer"),
        "citations": response.get("citations", []),
        "used_chunks_count": response.get("used_chunks_count", 0),
        "latency_ms": response.get("latency_ms", 0),
        "mode": response.get("mode"),
        "debug_info": response.get("debug_info"),
    }

