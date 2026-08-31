from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_enterprise_mcp.exceptions import ValidationError


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("Expected a list of strings.")
    output: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            output.append(text)
    return output


def _string_map(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError("Expected an object for metadata_filters.")
    output: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        mapped = str(raw_value).strip()
        if key and mapped:
            output[key] = mapped
    return output or None


@dataclass
class SearchFilters:
    source_type: str | None = None
    source_id: int | None = None
    source_part_id: int | None = None
    locator_filter: str | None = None
    metadata_filters: dict[str, str] | None = None

    def to_backend(self) -> dict[str, Any] | None:
        payload = {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "source_part_id": self.source_part_id,
            "locator_filter": self.locator_filter,
            "metadata_filters": self.metadata_filters,
        }
        cleaned = {key: value for key, value in payload.items() if value not in (None, "", {})}
        return cleaned or None

    @classmethod
    def from_input(cls, payload: Any) -> "SearchFilters | None":
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValidationError("filters must be an object.")
        return cls(
            source_type=_optional_str(payload.get("source_type")),
            source_id=_optional_int(payload.get("source_id")),
            source_part_id=_optional_int(payload.get("source_part_id")),
            locator_filter=_optional_str(payload.get("locator_filter")),
            metadata_filters=_string_map(payload.get("metadata_filters")),
        )


@dataclass
class AskGroundedInput:
    question: str
    k_chunks: int = 6
    mode: str | None = None
    filters: SearchFilters | None = None
    deep_research: bool = False
    custom_query: str | None = None
    anchor_terms: list[str] = field(default_factory=list)
    exact_phrase_bias: str | None = None
    expand_neighbors: bool = False
    dry_run: bool = False
    force_rare_keyword_scan: bool = False

    @classmethod
    def from_input(cls, payload: dict[str, Any]) -> "AskGroundedInput":
        question = _optional_str(payload.get("question"))
        if not question:
            raise ValidationError("question is required.")
        k_chunks = int(payload.get("k_chunks", 6))
        if k_chunks < 1 or k_chunks > 20:
            raise ValidationError("k_chunks must be between 1 and 20.")
        return cls(
            question=question,
            k_chunks=k_chunks,
            mode=_optional_str(payload.get("mode")),
            filters=SearchFilters.from_input(payload.get("filters")),
            deep_research=_optional_bool(payload.get("deep_research")),
            custom_query=_optional_str(payload.get("custom_query")),
            anchor_terms=_string_list(payload.get("anchor_terms")),
            exact_phrase_bias=_optional_str(payload.get("exact_phrase_bias")),
            expand_neighbors=_optional_bool(payload.get("expand_neighbors")),
            dry_run=_optional_bool(payload.get("dry_run")),
            force_rare_keyword_scan=_optional_bool(payload.get("force_rare_keyword_scan")),
        )

    def to_backend(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "k_chunks": self.k_chunks,
            "mode": self.mode,
            "filters": self.filters.to_backend() if self.filters else None,
            "deep_research": self.deep_research,
            "custom_query": self.custom_query,
            "anchor_terms": self.anchor_terms,
            "exact_phrase_bias": self.exact_phrase_bias,
            "expand_neighbors": self.expand_neighbors,
            "dry_run": self.dry_run,
            "force_rare_keyword_scan": self.force_rare_keyword_scan,
        }


@dataclass
class SearchDocumentsInput:
    question: str
    k: int = 8
    mode: str | None = None
    filters: SearchFilters | None = None
    deep_research: bool = False
    custom_query: str | None = None
    anchor_terms: list[str] = field(default_factory=list)
    exact_phrase_bias: str | None = None
    expand_neighbors: bool = False
    force_rare_keyword_scan: bool = False
    debug: bool = False

    @classmethod
    def from_input(cls, payload: dict[str, Any]) -> "SearchDocumentsInput":
        question = _optional_str(payload.get("question"))
        if not question:
            raise ValidationError("question is required.")
        k = int(payload.get("k", 8))
        if k < 1 or k > 50:
            raise ValidationError("k must be between 1 and 50.")
        return cls(
            question=question,
            k=k,
            mode=_optional_str(payload.get("mode")),
            filters=SearchFilters.from_input(payload.get("filters")),
            deep_research=_optional_bool(payload.get("deep_research")),
            custom_query=_optional_str(payload.get("custom_query")),
            anchor_terms=_string_list(payload.get("anchor_terms")),
            exact_phrase_bias=_optional_str(payload.get("exact_phrase_bias")),
            expand_neighbors=_optional_bool(payload.get("expand_neighbors")),
            force_rare_keyword_scan=_optional_bool(payload.get("force_rare_keyword_scan")),
            debug=_optional_bool(payload.get("debug")),
        )

    def to_backend(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "k": self.k,
            "mode": self.mode,
            "filters": self.filters.to_backend() if self.filters else None,
            "deep_research": self.deep_research,
            "custom_query": self.custom_query,
            "anchor_terms": self.anchor_terms,
            "exact_phrase_bias": self.exact_phrase_bias,
            "expand_neighbors": self.expand_neighbors,
            "force_rare_keyword_scan": self.force_rare_keyword_scan,
            "debug": self.debug,
        }


@dataclass
class GetDocumentExcerptInput:
    question: str
    source_id: int | None = None
    source_part_id: int | None = None
    locator_filter: str | None = None
    max_chars: int = 1200
    mode: str | None = "keyword"
    metadata_filters: dict[str, str] | None = None

    @classmethod
    def from_input(cls, payload: dict[str, Any]) -> "GetDocumentExcerptInput":
        question = _optional_str(payload.get("question"))
        if not question:
            raise ValidationError("question is required.")
        source_id = _optional_int(payload.get("source_id"))
        source_part_id = _optional_int(payload.get("source_part_id"))
        locator_filter = _optional_str(payload.get("locator_filter"))
        if source_id is None and source_part_id is None and locator_filter is None:
            raise ValidationError("At least one of source_id, source_part_id, or locator_filter is required.")
        max_chars = int(payload.get("max_chars", 1200))
        if max_chars < 100 or max_chars > 4000:
            raise ValidationError("max_chars must be between 100 and 4000.")
        return cls(
            question=question,
            source_id=source_id,
            source_part_id=source_part_id,
            locator_filter=locator_filter,
            max_chars=max_chars,
            mode=_optional_str(payload.get("mode")) or "keyword",
            metadata_filters=_string_map(payload.get("metadata_filters")),
        )

    def to_search_backend(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "k": 1,
            "mode": self.mode,
            "filters": SearchFilters(
                source_id=self.source_id,
                source_part_id=self.source_part_id,
                locator_filter=self.locator_filter,
                metadata_filters=self.metadata_filters,
            ).to_backend(),
            "debug": False,
            "deep_research": False,
            "anchor_terms": [],
            "expand_neighbors": False,
            "force_rare_keyword_scan": False,
        }

