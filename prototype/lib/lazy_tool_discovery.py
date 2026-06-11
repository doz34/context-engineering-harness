"""
CE-Harness Lazy Tool Discovery Engine
======================================
On-demand tool loading to reduce context pollution from large tool catalogs.
Keyword-indexed search, deferred definition loading, similarity deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolDescriptor:
    """Metadata-only handle for a tool. Definition loaded on demand."""

    name: str
    description: str
    keywords: set[str]
    definition_loader: Callable[[], dict]

    _definition: dict | None = field(default=None, init=False, repr=False)

    def load(self) -> dict:
        if self._definition is None:
            self._definition = self.definition_loader()
        return self._definition


class ToolDiscoveryEngine:
    """
    Lazy tool registry with keyword search and token-aware loading.

    Tools are registered with metadata + a loader callable. Full definitions
    are fetched only when needed, keeping the active context small.
    """

    AVG_DEFINITION_TOKENS = 150  # rough estimate per tool definition

    def __init__(self, max_context_tools: int = 20) -> None:
        self.max_context_tools = max_context_tools
        self._registry: dict[str, ToolDescriptor] = {}
        self._index: dict[str, set[str]] = {}  # keyword -> set of tool names
        self._loaded: set[str] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        keywords: set[str],
        definition_loader: Callable[[], dict],
    ) -> None:
        """Register a tool with lazy definition."""
        desc = ToolDescriptor(
            name=name,
            description=description,
            keywords=keywords,
            definition_loader=definition_loader,
        )
        self._registry[name] = desc
        for kw in keywords:
            self._index.setdefault(kw, set()).add(name)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[ToolDescriptor]:
        """Keyword scoring search. Returns descriptors (metadata only)."""
        query_words = set(query.lower().split())
        scores: dict[str, int] = {}
        for word in query_words:
            for tool_name in self._index.get(word, set()):
                scores[tool_name] = scores.get(tool_name, 0) + 1

        ranked = sorted(scores, key=lambda n: scores[n], reverse=True)[:top_k]
        return [self._registry[n] for n in ranked if n in self._registry]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_definition(self, tool_name: str) -> dict:
        """Load full definition on demand."""
        desc = self._registry[tool_name]
        defn = desc.load()
        self._loaded.add(tool_name)
        return defn

    def get_relevant_tools(self, query: str, top_k: int = 5) -> list[dict]:
        """Search + load definitions for the top-k results."""
        results = self.search(query, top_k=top_k)
        definitions: list[dict] = []
        for desc in results:
            if len(self._loaded) >= self.max_context_tools:
                break
            definitions.append(self.load_definition(desc.name))
        return definitions

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(text.lower().split())

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    def deduplicate(self, tools: list[ToolDescriptor]) -> list[ToolDescriptor]:
        """Remove tools with >80% description overlap (Jaccard)."""
        kept: list[ToolDescriptor] = []
        seen_tokens: list[set[str]] = []
        for tool in tools:
            tokens = self._tokenize(tool.description)
            is_dup = any(self._jaccard(tokens, st) > 0.8 for st in seen_tokens)
            if not is_dup:
                kept.append(tool)
                seen_tokens.append(tokens)
        return kept

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return registry size, loaded count, estimated token savings."""
        registered = len(self._registry)
        loaded = len(self._loaded)
        avg = self.AVG_DEFINITION_TOKENS
        return {
            "registered": registered,
            "loaded": loaded,
            "token_savings": (registered - loaded) * avg,
        }
