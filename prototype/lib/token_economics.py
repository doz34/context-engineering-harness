"""
CE-Harness Token Economics Manager
====================================
Multi-agent token cost optimization based on Anthropic research.

Implements:
- 15× multiplier awareness (fan-out cost)
- Model selection per subagent role
- Decision framework: single-agent vs multi-agent

v1.1 — Extracted from context-engineering-research corpus.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ModelProfile:
    """Cost and capability profile for an LLM model."""
    name: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    context_window: int
    speed_tok_per_sec: int

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given token usage."""
        return (input_tokens / 1000 * self.cost_per_1k_input
                + output_tokens / 1000 * self.cost_per_1k_output)


class TokenEconomicsManager:
    """Manage token economics for multi-agent systems.

    Helps decide when to deploy multi-agent vs single-agent,
    and which model to assign to each subtask.

    Usage:
        econ = TokenEconomicsManager(baseline_budget=100_000)
        rec = econ.should_deploy_multi_agent("parallel_search", 50_000)
        models = econ.optimize_subagent_models(["search", "synthesis", "code"])
    """

    # Predefined model profiles (Anthropic pricing, approximate)
    OPUS = ModelProfile("opus", 0.015, 0.075, 200_000, 30)
    SONNET = ModelProfile("sonnet", 0.003, 0.015, 200_000, 80)
    HAIKU = ModelProfile("haiku", 0.001, 0.005, 200_000, 200)

    # Task type → recommended model
    TASK_MODEL_MAP = {
        "search": "haiku",
        "synthesis": "opus",
        "code": "sonnet",
        "review": "sonnet",
        "simple": "haiku",
    }

    def __init__(self, baseline_budget: int = 100_000):
        self.baseline_budget = baseline_budget
        self._models: Dict[str, ModelProfile] = {
            "opus": self.OPUS,
            "sonnet": self.SONNET,
            "haiku": self.HAIKU,
        }

    def register_model(self, profile: ModelProfile) -> None:
        """Register a model profile."""
        self._models[profile.name] = profile

    def get_model(self, name: str) -> Optional[ModelProfile]:
        """Get a registered model profile."""
        return self._models.get(name)

    def should_deploy_multi_agent(self, task_complexity: str,
                                  estimated_tokens: int) -> Dict:
        """Decide: single agent vs multi-agent.

        Returns dict with:
        - recommendation: "single" or "multi"
        - reasoning: human-readable explanation
        - estimated_cost_tokens: total token budget needed
        """
        # Single agent is better for small or sequential tasks
        if estimated_tokens < 10_000:
            return {
                "recommendation": "single",
                "reasoning": (f"Task estimated at {estimated_tokens:,} tokens "
                              f"(< 10K threshold). Single agent sufficient."),
                "estimated_cost_tokens": estimated_tokens,
            }

        # Multi-agent if parallelizable and budget allows
        is_parallel = task_complexity in (
            "parallel_search", "code_review", "multi_source_analysis",
            "fan_out", "distributed", "parallel",
        )

        fanout_cost = self.calculate_fanout_cost(
            agent_count=3, avg_tokens_per_agent=estimated_tokens // 3
        )

        if is_parallel and fanout_cost <= self.baseline_budget:
            return {
                "recommendation": "multi",
                "reasoning": (f"Task is '{task_complexity}' with "
                              f"{estimated_tokens:,} tokens. "
                              f"Multi-agent recommended. "
                              f"Fan-out cost: {fanout_cost:,} tokens "
                              f"(15% overhead)."),
                "estimated_cost_tokens": fanout_cost,
            }

        return {
            "recommendation": "single",
            "reasoning": (f"Task is '{task_complexity}' but not clearly "
                          f"parallelizable or budget insufficient for "
                          f"multi-agent (fan-out cost {fanout_cost:,} > "
                          f"budget {self.baseline_budget:,})."),
            "estimated_cost_tokens": estimated_tokens,
        }

    def optimize_subagent_models(
            self, subtasks: List[str]
    ) -> List[Tuple[str, ModelProfile]]:
        """Assign optimal model to each subtask.

        Returns list of (subtask, model_profile).
        """
        result = []
        for task in subtasks:
            model_name = self.TASK_MODEL_MAP.get(task, "sonnet")
            profile = self._models.get(model_name, self.SONNET)
            result.append((task, profile))
        return result

    def calculate_fanout_cost(self, agent_count: int,
                              avg_tokens_per_agent: int,
                              overhead_pct: float = 0.15) -> int:
        """Calculate total token cost of a fan-out.

        Includes orchestration overhead (default 15%).
        The 15× multiplier is the worst case for uncontrolled fan-out.
        """
        base_cost = agent_count * avg_tokens_per_agent
        overhead = int(base_cost * overhead_pct)
        return base_cost + overhead

    def budget_report(self, used_tokens: int) -> Dict:
        """Return budget utilization report."""
        remaining = max(0, self.baseline_budget - used_tokens)
        pct = (used_tokens / max(1, self.baseline_budget)) * 100
        return {
            "budget_total": self.baseline_budget,
            "budget_used": used_tokens,
            "budget_remaining": remaining,
            "utilization_pct": round(pct, 1),
            "status": (
                "OK" if pct < 70
                else "WARNING" if pct < 90
                else "CRITICAL"
            ),
        }

    def recommend_model_for(self, task_type: str) -> ModelProfile:
        """Recommend a model based on task type."""
        model_name = self.TASK_MODEL_MAP.get(task_type, "sonnet")
        return self._models.get(model_name, self.SONNET)
