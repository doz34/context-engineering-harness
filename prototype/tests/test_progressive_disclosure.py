"""Tests for progressive disclosure engine."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.progressive_disclosure import ProgressiveDisclosureEngine


class TestRegisterSkill:
    def test_stores_metadata(self):
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("code_review", "Reviews code for bugs",
                              keywords=["review", "code", "bugs"])
        meta = engine.get_metadata_all()
        assert len(meta) == 1
        assert meta[0]["name"] == "code_review"


class TestGetMetadataAll:
    def test_returns_lightweight(self):
        engine = ProgressiveDisclosureEngine()
        for i in range(5):
            engine.register_skill(f"skill_{i}", f"Description {i}")
        meta = engine.get_metadata_all()
        assert len(meta) == 5
        for m in meta:
            assert "tokens" in m
            assert m["tokens"] > 0


class TestEvaluateRelevance:
    def test_ranks_correctly(self):
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("code_review", "Code review",
                              keywords=["code", "review", "bugs"])
        engine.register_skill("deploy", "Deploy to production",
                              keywords=["deploy", "production", "ci"])
        engine.register_skill("security", "Security audit",
                              keywords=["security", "audit", "vulnerability"])

        results = engine.evaluate_relevance("review my code for bugs")
        assert len(results) > 0
        assert results[0]["name"] == "code_review"

    def test_top_k_limits_results(self):
        engine = ProgressiveDisclosureEngine()
        for i in range(10):
            engine.register_skill(f"skill_{i}", f"Skill {i}",
                                  keywords=[f"kw_{i}"])
        results = engine.evaluate_relevance("kw_0 kw_1 kw_2", top_k=2)
        assert len(results) <= 2


class TestLoadBody:
    def test_returns_full_content(self):
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("test", "Test skill",
                              body_loader=lambda: "Full body content here")
        body = engine.load_body("test")
        assert body == "Full body content here"

    def test_nonexistent_skill_returns_empty(self):
        engine = ProgressiveDisclosureEngine()
        assert engine.load_body("missing") == ""


class TestLoadResource:
    def test_on_demand(self):
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("test", "Test",
                              resource_loader=lambda p: f"Resource: {p}")
        result = engine.load_resource("test", "data.csv")
        assert result == "Resource: data.csv"


class TestStats:
    def test_reports_accurate_counts(self):
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("a", "Skill A", keywords=["x", "y"])
        engine.register_skill("b", "Skill B", keywords=["y", "z"])
        stats = engine.stats()
        assert stats["registered_skills"] == 2
        assert stats["keyword_index_size"] == 3  # x, y, z


class TestEmptyEngine:
    def test_returns_empty(self):
        engine = ProgressiveDisclosureEngine()
        assert engine.get_metadata_all() == []
        assert engine.evaluate_relevance("test") == []
        assert engine.load_body("test") == ""
        assert engine.stats()["registered_skills"] == 0
