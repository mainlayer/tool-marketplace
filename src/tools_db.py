"""
In-memory tool registry with five built-in sample tools.

In production this would be backed by PostgreSQL / DynamoDB.
The interface is kept async-ready so swapping the backend requires
only this module.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import AccessRecord, ToolCategory, ToolRecord


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Sample tool definitions
# ---------------------------------------------------------------------------

_SAMPLE_TOOLS: List[dict] = [
    {
        "id": "tool-web-search-001",
        "name": "Web Search",
        "description": (
            "Perform real-time web searches and get structured results. "
            "Returns titles, URLs, snippets, and optional full-page text. "
            "Ideal for agents that need up-to-date information."
        ),
        "price_usdc": 0.002,
        "category": ToolCategory.SEARCH,
        "tags": ["search", "web", "information", "real-time"],
        "mcp_endpoint": "https://tools.example.com/mcp/web-search",
        "tool_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "include_full_text": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
        "vendor_id": "vendor-sample-001",
        "mainlayer_resource_id": "res_web_search_sample",
    },
    {
        "id": "tool-calculator-001",
        "name": "Advanced Calculator",
        "description": (
            "Evaluate mathematical expressions, symbolic algebra, unit conversions, "
            "and statistical functions. Powered by a sandboxed math engine — no code "
            "execution on your infrastructure required."
        ),
        "price_usdc": 0.0005,
        "category": ToolCategory.UTILITIES,
        "tags": ["math", "calculator", "algebra", "statistics"],
        "mcp_endpoint": "https://tools.example.com/mcp/calculator",
        "tool_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate, e.g. 'sqrt(144) + 2^8'",
                },
                "precision": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["expression"],
        },
        "vendor_id": "vendor-sample-001",
        "mainlayer_resource_id": "res_calculator_sample",
    },
    {
        "id": "tool-weather-001",
        "name": "Weather Forecast",
        "description": (
            "Current conditions and multi-day forecasts for any city or GPS coordinate. "
            "Returns temperature, humidity, wind, UV index, and precipitation probability. "
            "Supports metric and imperial units."
        ),
        "price_usdc": 0.001,
        "category": ToolCategory.DATA,
        "tags": ["weather", "forecast", "climate", "location"],
        "mcp_endpoint": "https://tools.example.com/mcp/weather",
        "tool_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or 'lat,lon' coordinate pair",
                },
                "days": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 14,
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "default": "metric",
                },
            },
            "required": ["location"],
        },
        "vendor_id": "vendor-sample-002",
        "mainlayer_resource_id": "res_weather_sample",
    },
    {
        "id": "tool-translate-001",
        "name": "Language Translator",
        "description": (
            "Translate text between 100+ languages with automatic source detection. "
            "Supports plain text and HTML. Returns the translated text along with "
            "confidence scores and detected source language."
        ),
        "price_usdc": 0.003,
        "category": ToolCategory.COMMUNICATION,
        "tags": ["translate", "language", "nlp", "i18n"],
        "mcp_endpoint": "https://tools.example.com/mcp/translate",
        "tool_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 10000},
                "target_language": {
                    "type": "string",
                    "description": "ISO 639-1 language code, e.g. 'es', 'fr', 'ja'",
                },
                "source_language": {
                    "type": "string",
                    "description": "Optional. Auto-detected if omitted.",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "html"],
                    "default": "text",
                },
            },
            "required": ["text", "target_language"],
        },
        "vendor_id": "vendor-sample-002",
        "mainlayer_resource_id": "res_translate_sample",
    },
    {
        "id": "tool-summarize-001",
        "name": "Document Summarizer",
        "description": (
            "Generate concise summaries of long documents, articles, or any text. "
            "Choose between extractive and abstractive modes. Returns a summary with "
            "key points and optional sentiment analysis."
        ),
        "price_usdc": 0.005,
        "category": ToolCategory.AI,
        "tags": ["summarize", "nlp", "ai", "text", "productivity"],
        "mcp_endpoint": "https://tools.example.com/mcp/summarize",
        "tool_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 100000},
                "max_sentences": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "mode": {
                    "type": "string",
                    "enum": ["extractive", "abstractive"],
                    "default": "abstractive",
                },
                "include_key_points": {"type": "boolean", "default": True},
                "include_sentiment": {"type": "boolean", "default": False},
            },
            "required": ["text"],
        },
        "vendor_id": "vendor-sample-003",
        "mainlayer_resource_id": "res_summarize_sample",
    },
]


class ToolsDB:
    """Thread-safe in-memory store for tools and access records."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolRecord] = {}
        self._access: Dict[str, AccessRecord] = {}
        self._seed()

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def _seed(self) -> None:
        now = _now()
        for raw in _SAMPLE_TOOLS:
            record = ToolRecord(
                **raw,
                created_at=now,
                updated_at=now,
            )
            self._tools[record.id] = record

    # ------------------------------------------------------------------
    # Tools CRUD
    # ------------------------------------------------------------------

    def create_tool(self, data: dict) -> ToolRecord:
        now = _now()
        record = ToolRecord(
            id=_new_id(),
            created_at=now,
            updated_at=now,
            **data,
        )
        self._tools[record.id] = record
        return record

    def get_tool(self, tool_id: str) -> Optional[ToolRecord]:
        return self._tools.get(tool_id)

    def list_tools(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> tuple[List[ToolRecord], int]:
        results = list(self._tools.values())

        if active_only:
            results = [t for t in results if t.active]

        if category:
            results = [t for t in results if t.category.value == category]

        if tag:
            results = [t for t in results if tag.lower() in t.tags]

        if search:
            q = search.lower()
            results = [
                t
                for t in results
                if q in t.name.lower() or q in t.description.lower()
            ]

        total = len(results)
        start = (page - 1) * page_size
        return results[start : start + page_size], total

    def increment_call_count(self, tool_id: str) -> None:
        if tool_id in self._tools:
            self._tools[tool_id].call_count += 1
            self._tools[tool_id].updated_at = _now()

    # ------------------------------------------------------------------
    # Access records
    # ------------------------------------------------------------------

    def create_access(self, data: dict) -> AccessRecord:
        record = AccessRecord(**data)
        self._access[record.access_token] = record
        return record

    def get_access(self, token: str) -> Optional[AccessRecord]:
        return self._access.get(token)

    def decrement_access(self, token: str) -> Optional[AccessRecord]:
        record = self._access.get(token)
        if record and record.calls_remaining > 0:
            record.calls_remaining -= 1
            return record
        return None

    # ------------------------------------------------------------------
    # Category counts
    # ------------------------------------------------------------------

    def category_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for t in self._tools.values():
            if t.active:
                counts[t.category.value] = counts.get(t.category.value, 0) + 1
        return counts


# Singleton
_db: Optional[ToolsDB] = None


def get_db() -> ToolsDB:
    global _db
    if _db is None:
        _db = ToolsDB()
    return _db
