# Contributing

Thank you for improving the governed RAG MCP integration layer. This server exposes a
small read-only tool boundary between the agent and backend. It must not acquire database
access, implement retrieval policy, or bypass backend authentication and access control.

The runtime is deliberately pure Python standard library. Do not add a runtime dependency
without explicit approval; `dependencies = []` in `pyproject.toml` is an architectural
contract rather than an unfinished dependency list.

## Development setup

Use Python 3.12 for development while preserving the package's Python 3.9 compatibility.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The tests use fakes and make no network calls, so they do not require a running backend.
Do not commit backend tokens, local-login credentials, `.env` files, or response data.

## Before opening a pull request

Run:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Install and run the repository hooks when contributing locally:

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

CI runs three required jobs: `lint`, `test`, and `security`. They enforce formatting and
static lint rules, run the offline MCP suite, and scan committed history for secrets.

Changes to tool schemas or backend payloads must include contract-focused tests covering
valid input, invalid input, and backend failure behaviour. Preserve structured JSON-RPC
errors and the distinctions between authentication, timeout, transport, and validation
failures.

## Protected branch policy

Changes to `main` should go through a pull request with all required CI checks passing,
all review conversations resolved, and a CODEOWNERS review when an eligible second
maintainer is available. Force pushes and branch deletion are disabled. A solo owner
cannot approve their own pull request, so mandatory approving reviews should only be
enabled after another maintainer has been granted access.
