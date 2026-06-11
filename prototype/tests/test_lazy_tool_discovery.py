"""
Tests for Lazy Tool Discovery Engine.
"""

import pytest

from lib.lazy_tool_discovery import ToolDescriptor, ToolDiscoveryEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loader(data: dict):
    """Return a callable that yields *data* and records call count."""
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return data

    loader.calls = calls
    return loader


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegisterToolBuildsIndex:
    def test_tool_appears_in_registry(self):
        eng = ToolDiscoveryEngine()
        eng.register_tool("read_file", "Read a file", {"file", "read"}, dict)
        assert "read_file" in eng._registry

    def test_keywords_indexed(self):
        eng = ToolDiscoveryEngine()
        eng.register_tool("read_file", "Read a file", {"file", "read"}, dict)
        assert "read_file" in eng._index.get("file", set())
        assert "read_file" in eng._index.get("read", set())


class TestSearchFindsRelevantTools:
    def test_keyword_match_ranks_higher(self):
        eng = ToolDiscoveryEngine()
        eng.register_tool("a", "Tool a", {"file"}, dict)
        eng.register_tool("b", "Tool b", {"file", "read"}, dict)
        results = eng.search("read file")
        names = [t.name for t in results]
        assert names.index("b") < names.index("a")

    def test_no_match_returns_empty(self):
        eng = ToolDiscoveryEngine()
        eng.register_tool("x", "Tool x", {"network"}, dict)
        assert eng.search("database") == []


class TestSearchReturnsMetadataOnly:
    def test_definitions_not_loaded_by_search(self):
        loader = _make_loader({"inputSchema": {}})
        eng = ToolDiscoveryEngine()
        eng.register_tool("t", "desc", {"kw"}, loader)
        results = eng.search("kw")
        assert len(results) == 1
        assert loader.calls["n"] == 0  # loader never called
        assert results[0].name == "t"
        assert isinstance(results[0], ToolDescriptor)


class TestLoadDefinitionCallsLoader:
    def test_loader_invoked_once(self):
        loader = _make_loader({"inputSchema": {"type": "object"}})
        eng = ToolDiscoveryEngine()
        eng.register_tool("t", "desc", {"kw"}, loader)
        defn = eng.load_definition("t")
        assert defn == {"inputSchema": {"type": "object"}}
        assert loader.calls["n"] == 1

    def test_cached_on_second_call(self):
        loader = _make_loader({"x": 1})
        eng = ToolDiscoveryEngine()
        eng.register_tool("t", "desc", {"kw"}, loader)
        eng.load_definition("t")
        eng.load_definition("t")
        assert loader.calls["n"] == 1  # not called again


class TestGetRelevantToolsLoadsTopK:
    def test_loads_exactly_top_k(self):
        eng = ToolDiscoveryEngine()
        for i in range(5):
            eng.register_tool(f"t{i}", f"Tool {i}", {"search"}, lambda i=i: {"id": i})
        defs = eng.get_relevant_tools("search", top_k=3)
        assert len(defs) == 3


class TestDeduplicateRemovesSimilar:
    def test_near_duplicates_removed(self):
        eng = ToolDiscoveryEngine()
        tools = [
            ToolDescriptor("a", "read file from disk and return contents", {"file"}, dict),
            ToolDescriptor("b", "read file from disk and return contents quickly", {"file"}, dict),
        ]
        deduped = eng.deduplicate(tools)
        assert len(deduped) == 1
        assert deduped[0].name == "a"

    def test_distinct_tools_kept(self):
        eng = ToolDiscoveryEngine()
        tools = [
            ToolDescriptor("a", "read files from disk", {"file"}, dict),
            ToolDescriptor("b", "send email notifications", {"email"}, dict),
        ]
        assert len(eng.deduplicate(tools)) == 2


class TestStatsReportsTokenSavings:
    def test_savings_decrease_as_tools_loaded(self):
        eng = ToolDiscoveryEngine()
        for i in range(10):
            eng.register_tool(f"t{i}", f"Tool {i}", {"kw"}, dict)

        s1 = eng.stats()
        assert s1["registered"] == 10
        assert s1["loaded"] == 0
        assert s1["token_savings"] == 10 * 150

        eng._loaded.add("t0")
        s2 = eng.stats()
        assert s2["token_savings"] == 9 * 150


class TestMaxContextToolsEnforced:
    def test_get_relevant_tools_respects_cap(self):
        eng = ToolDiscoveryEngine(max_context_tools=2)
        for i in range(5):
            eng.register_tool(f"t{i}", f"Tool {i}", {"search"}, lambda i=i: {"id": i})
        defs = eng.get_relevant_tools("search", top_k=5)
        assert len(defs) == 2  # capped at max_context_tools
