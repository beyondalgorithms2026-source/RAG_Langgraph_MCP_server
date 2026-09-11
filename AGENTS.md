# Agent guide

Read [`README.md`](README.md) and
[`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md) before changing this repository.
The canonical cross-repository standard is
[B004 engineering standards](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP/blob/main/docs/ENGINEERING_STANDARDS.md).
This local guide is sufficient for safe work when the APP repository is unavailable;
where rules overlap, the stricter rule applies.

## Scope and ownership

- This repository owns the thin JSON-RPC/HTTP integration boundary between APP and
  STARTER.
- Preserve the direct stdio JSON-RPC implementation and Python 3.9 compatibility.
- The runtime is pure Python standard library and has zero runtime dependencies.
- Do not add database access, retrieval policy, ACL decisions, citations, backend
  governance, or a path around backend authentication/authorization.
- Do not move orchestration or evidence validation here. APP owns those behaviours;
  STARTER owns retrieval and security policy.
- APP must never receive database credentials or access STARTER/PostgreSQL directly.
- The private-assets repository is permanently out of scope.

Do not introduce Redis, read replicas, pub/sub, asymmetric JWT, Jest, new services, new
dependencies, or comparable architecture changes unless they are already part of B004
or separately approved.

## Before implementation

1. Identify whether the change belongs at the integration boundary before editing.
2. Identify authentication, malformed-input, readiness, timeout, retry, compatibility,
   prompt-injection, and data-leakage risks.
3. Add or identify a meaningful test before or alongside the implementation.
4. Preserve published tool names, JSON-RPC compatibility, backend request/response
   shapes, and structured error categories.
5. Ask before adding any dependency or changing an architecture/security boundary.

## Security and error invariants

- Never commit secrets, tokens, connection strings, `.env` files, private corpus data,
  backend responses, or unsanitized diagnostics.
- Treat request parameters, backend responses, and error bodies as untrusted.
- Forward authentication without inventing authorization policy or bypassing backend
  enforcement.
- Preserve structured distinctions between validation, authentication, readiness,
  timeout, retry exhaustion, transport, and backend failures. Do not convert them into a
  plausible tool success or leak raw backend diagnostics.
- Keep retries bounded and safe. Readiness retries must not duplicate a potentially paid
  or stateful backend request.
- Never weaken error, authentication, or compatibility behaviour merely to make a test
  pass.

## Test protocol

- Tests must validate meaningful behaviour; do not add placeholder or always-passing
  assertions.
- Cover malformed JSON-RPC, missing and invalid parameters, authentication failures,
  readiness, bounded retries, timeouts, retry exhaustion, response parsing, and tool
  contract drift where relevant.
- Fakes are appropriate for deterministic integration-boundary tests. They do not prove
  live retrieval, SQL ACL enforcement, or full-stack answer quality.
- P12 is APP's fast mocked evaluation-harness smoke test. P12B is the authoritative real
  APP → MCP → STARTER → PostgreSQL/pgvector 25-question regression gate.
- Distinguish infrastructure/transport failures from answer-quality failures, and never
  automatically overwrite a P12B baseline after regression.

## API and tool-route review

For a changed JSON-RPC method, backend route mapping, or tool schema, explicitly check
input validation and bounds, authentication forwarding, untrusted-content handling,
diagnostic redaction, timeout/retry behaviour, response compatibility, and whether unit,
contract, red-team, or P12B coverage is required.

## Verification and completion

Run:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

A change is complete only when relevant tests and formatting pass, zero runtime
dependencies and repository boundaries remain intact, tool contracts remain compatible,
the applicable P12B result meets its approved baseline, documentation/version metadata
are current, and actual failures and skips are reported honestly. Documentation is
guidance, not enforcement; name a rule as enforced only when a mechanical check verifies
it.
