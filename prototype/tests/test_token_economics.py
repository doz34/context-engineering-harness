"""Tests for token economics manager."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.token_economics import TokenEconomicsManager, ModelProfile


class TestRegisterModel:
    def test_register_model(self):
        econ = TokenEconomicsManager()
        profile = ModelProfile("test", 0.01, 0.05, 100_000, 50)
        econ.register_model(profile)
        assert econ.get_model("test") is not None
        assert econ.get_model("test").name == "test"


class TestShouldDeployMultiAgent:
    def test_small_task_single_agent(self):
        econ = TokenEconomicsManager()
        rec = econ.should_deploy_multi_agent("simple_query", 5_000)
        assert rec["recommendation"] == "single"

    def test_large_parallel_multi_agent(self):
        econ = TokenEconomicsManager(baseline_budget=1_000_000)
        rec = econ.should_deploy_multi_agent("parallel_search", 50_000)
        assert rec["recommendation"] == "multi"
        assert rec["estimated_cost_tokens"] > 0


class TestOptimizeSubagentModels:
    def test_routing_search_to_haiku(self):
        econ = TokenEconomicsManager()
        result = econ.optimize_subagent_models(["search"])
        assert result[0][1].name == "haiku"

    def test_routing_synthesis_to_opus(self):
        econ = TokenEconomicsManager()
        result = econ.optimize_subagent_models(["synthesis"])
        assert result[0][1].name == "opus"

    def test_routing_code_to_sonnet(self):
        econ = TokenEconomicsManager()
        result = econ.optimize_subagent_models(["code"])
        assert result[0][1].name == "sonnet"


class TestCalculateFanoutCost:
    def test_cost_with_overhead(self):
        econ = TokenEconomicsManager()
        cost = econ.calculate_fanout_cost(agent_count=3, avg_tokens_per_agent=1000)
        expected = 3000 + int(3000 * 0.15)  # 3450
        assert cost == expected


class TestBudgetReport:
    def test_utilization(self):
        econ = TokenEconomicsManager(baseline_budget=100_000)
        report = econ.budget_report(used_tokens=50_000)
        assert report["utilization_pct"] == 50.0
        assert report["status"] == "OK"

    def test_critical_status(self):
        econ = TokenEconomicsManager(baseline_budget=100_000)
        report = econ.budget_report(used_tokens=95_000)
        assert report["status"] == "CRITICAL"


class TestRecommendModel:
    def test_recommend_model_for_task_types(self):
        econ = TokenEconomicsManager()
        assert econ.recommend_model_for("search").name == "haiku"
        assert econ.recommend_model_for("synthesis").name == "opus"
        assert econ.recommend_model_for("code").name == "sonnet"
        assert econ.recommend_model_for("review").name == "sonnet"
        assert econ.recommend_model_for("simple").name == "haiku"


class TestPredefinedModels:
    def test_predefined_models_exist(self):
        econ = TokenEconomicsManager()
        assert econ.get_model("opus") is not None
        assert econ.get_model("sonnet") is not None
        assert econ.get_model("haiku") is not None

    def test_model_cost_estimation(self):
        econ = TokenEconomicsManager()
        opus = econ.get_model("opus")
        cost = opus.estimate_cost(1000, 500)
        assert cost > 0
