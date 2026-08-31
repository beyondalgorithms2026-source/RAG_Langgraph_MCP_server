# RAG Enterprise MCP Server

Thin local MCP server that exposes a minimal tool layer over the existing
`RAG_ENTERPRISE_STARTER` backend.

## Phase 1 tool surface

- `ask_grounded` -> backend `POST /ask`
- `search_documents` -> backend `POST /search`
- `get_document_excerpt` -> backend `POST /search` with narrow filters

## Design rules

- No direct database access
- No duplicate retrieval logic
- No ACL or governance bypass
- All retrieval and authorization remain in the backend

## Environment

The server reads these environment variables:

- `RAG_BACKEND_BASE_URL` default `http://127.0.0.1:8000`
- `RAG_BACKEND_TIMEOUT_SECONDS` default `30`
- `RAG_BACKEND_BEARER_TOKEN` optional
- `RAG_BACKEND_DEV_LOGIN_EMAIL` optional
- `RAG_BACKEND_DEV_LOGIN_PASSWORD` optional
- `MCP_SERVER_NAME` default `rag-enterprise-mcp`
- `MCP_SERVER_VERSION` default `0.1.0`

## Local run

```bash
python3 -m rag_enterprise_mcp.server
```

## Claude Desktop example

Use the repo path in your Claude Desktop MCP config and pass any needed auth
environment variables there.

