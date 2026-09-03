# Enterprise RAG — MCP server

The integration layer of a three-part governed retrieval system. It is the **only** path
between the agent layer and the data layer, and it exists so that those two never talk
directly.

**This is one of three repositories.** Start here:
**[Governed RAG — agent layer](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP)**

## What problem this solves

An agent that can query a database directly can be talked into querying it differently.
Text retrieved from a document can carry instructions; a compromised or careless caller
can widen its own access. The defence is structural rather than behavioural: **give the
agent no database access at all.**

This server is that boundary made concrete. It exposes three read-only tools over the
Model Context Protocol and forwards them to the backend's HTTP API. It holds no database
credentials, executes no SQL, and cannot bypass the backend's authentication, access
control or citation rules — because it has no mechanism to.

## The three tools

| Tool | Purpose |
|---|---|
| `ask_grounded` | A grounded answer with citations, through the backend's own retrieval and access-control path |
| `search_documents` | Retrieval only, no generation |
| `get_document_excerpt` | A verbatim excerpt from a specific document |

`ask_grounded` accepts eleven parameters describing *what* to look for — question, mode,
candidate count, filters, anchor terms, neighbour expansion and so on.

It deliberately does **not** expose *how* retrieval behaves. Reranking, query rewriting,
expansion and fusion strategy are server-side settings an operator manages in the
backend. A caller can say what it needs; it cannot change retrieval policy. That
asymmetry is the point.

## What this is NOT

- Not deployed anywhere. Part of a self-built proof of concept with no users and no
  client deployment.
- Not a general-purpose MCP server. It speaks to one backend, over stdio, as a child
  process of the agent application.
- Not a security boundary on its own. It is one layer of a boundary the backend enforces.

## Implementation

Pure Python standard library — no third-party runtime dependencies. The MCP protocol is
implemented directly over stdio.

```bash
pip install -e .
```

It is launched automatically by the agent application, which spawns it as a child
process; you do not normally run it by hand.

## Licence

Apache-2.0.
