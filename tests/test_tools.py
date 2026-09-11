from __future__ import annotations

import unittest
from typing import Any

from rag_enterprise_mcp.exceptions import BackendError, ValidationError
from rag_enterprise_mcp.tools import ask_grounded, get_document_excerpt, search_documents


class _FakeClient:
    def __init__(
        self,
        *,
        ask_response: dict[str, Any] | None = None,
        search_response: dict[str, Any] | None = None,
        error: BackendError | None = None,
    ) -> None:
        self.ask_response = ask_response or {}
        self.search_response = search_response or {}
        self.error = error
        self.ask_payloads: list[dict[str, Any]] = []
        self.search_payloads: list[dict[str, Any]] = []

    def ask(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.ask_payloads.append(payload)
        if self.error:
            raise self.error
        return self.ask_response

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.search_payloads.append(payload)
        if self.error:
            raise self.error
        return self.search_response


class ToolTests(unittest.TestCase):
    def test_ask_grounded_builds_default_payload_and_projects_response(self) -> None:
        client = _FakeClient(
            ask_response={
                "answer": "Grounded answer",
                "citations": [{"source_id": 7}],
                "used_chunks_count": 2,
                "latency_ms": 14,
                "mode": "hybrid",
                "debug_info": {"trace": "safe-test-value"},
                "ignored": "not exposed",
            }
        )

        result = ask_grounded.run(client, {"question": "  What changed?  "})

        self.assertEqual(client.ask_payloads[0]["question"], "What changed?")
        self.assertEqual(client.ask_payloads[0]["k_chunks"], 6)
        self.assertFalse(client.ask_payloads[0]["deep_research"])
        self.assertEqual(result["answer"], "Grounded answer")
        self.assertNotIn("ignored", result)

    def test_ask_grounded_forwards_recovery_options(self) -> None:
        client = _FakeClient()
        ask_grounded.run(
            client,
            {
                "question": "Q",
                "k_chunks": 20,
                "mode": "keyword",
                "filters": {"source_id": "9", "metadata_filters": {"team": " hr "}},
                "deep_research": "yes",
                "custom_query": "  exact words  ",
                "anchor_terms": [" alpha ", "", "beta"],
                "exact_phrase_bias": "  quoted phrase ",
                "expand_neighbors": True,
                "dry_run": "true",
                "force_rare_keyword_scan": 1,
            },
        )

        payload = client.ask_payloads[0]
        self.assertEqual(payload["filters"], {"source_id": 9, "metadata_filters": {"team": "hr"}})
        self.assertEqual(payload["anchor_terms"], ["alpha", "beta"])
        self.assertEqual(payload["custom_query"], "exact words")
        self.assertTrue(payload["deep_research"])
        self.assertTrue(payload["dry_run"])

    def test_ask_grounded_requires_question(self) -> None:
        client = _FakeClient()
        with self.assertRaisesRegex(ValidationError, "question is required"):
            ask_grounded.run(client, {"question": "  "})
        self.assertEqual(client.ask_payloads, [])

    def test_ask_grounded_rejects_out_of_range_chunk_count(self) -> None:
        with self.assertRaisesRegex(ValidationError, "between 1 and 20"):
            ask_grounded.run(_FakeClient(), {"question": "Q", "k_chunks": 21})

    def test_search_documents_builds_defaults_and_projects_response(self) -> None:
        client = _FakeClient(
            search_response={"mode": "vector", "latency_ms": 8, "results": [{"id": 1}]}
        )

        result = search_documents.run(client, {"question": "Find policy"})

        self.assertEqual(client.search_payloads[0]["k"], 8)
        self.assertFalse(client.search_payloads[0]["debug"])
        self.assertEqual(result["results"], [{"id": 1}])
        self.assertIsNone(result["debug_info"])

    def test_search_documents_normalizes_filters_and_flags(self) -> None:
        client = _FakeClient()
        search_documents.run(
            client,
            {
                "question": "Q",
                "k": 50,
                "filters": {
                    "source_type": " pdf ",
                    "source_part_id": "12",
                    "locator_filter": " page:2 ",
                },
                "debug": "on",
                "expand_neighbors": "1",
            },
        )

        payload = client.search_payloads[0]
        self.assertEqual(
            payload["filters"],
            {"source_type": "pdf", "source_part_id": 12, "locator_filter": "page:2"},
        )
        self.assertTrue(payload["debug"])
        self.assertTrue(payload["expand_neighbors"])

    def test_search_documents_rejects_non_object_filters(self) -> None:
        with self.assertRaisesRegex(ValidationError, "filters must be an object"):
            search_documents.run(_FakeClient(), {"question": "Q", "filters": ["bad"]})

    def test_excerpt_requires_a_document_locator(self) -> None:
        with self.assertRaisesRegex(ValidationError, "At least one"):
            get_document_excerpt.run(_FakeClient(), {"question": "Q"})

    def test_excerpt_returns_unmatched_shape_for_empty_results(self) -> None:
        client = _FakeClient(search_response={"results": []})

        result = get_document_excerpt.run(client, {"question": "Q", "source_id": 3})

        self.assertFalse(result["matched"])
        self.assertIsNone(result["excerpt"])
        self.assertEqual(client.search_payloads[0]["filters"], {"source_id": 3})
        self.assertEqual(client.search_payloads[0]["k"], 1)

    def test_excerpt_truncates_the_top_result_without_mutating_backend_response(self) -> None:
        original = {"source_id": 3, "snippet": "x" * 150}
        client = _FakeClient(search_response={"results": [original]})

        result = get_document_excerpt.run(
            client, {"question": "Q", "source_part_id": 4, "max_chars": 100}
        )

        self.assertTrue(result["matched"])
        self.assertEqual(result["excerpt"], "x" * 100)
        self.assertEqual(original["snippet"], "x" * 150)


if __name__ == "__main__":
    unittest.main()
