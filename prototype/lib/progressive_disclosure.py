"""
CE-Harness Progressive Disclosure Engine
==========================================
3-level context loading from Anthropic's Agent Skills research.

Level 1: Always-loaded metadata (~100 tokens/skill) — in system prompt
Level 2: Conditional body loading (<5K tokens) — loaded when relevant
Level 3: Unlimited resources on demand — tool-call only

v1.1 — Extracted from context-engineering-research corpus.
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SkillDescriptor:
    """Metadata for a skill (Level 1 — always loaded)."""
    name: str
    description: str  # ~100 tokens, always in context
    keywords: List[str] = field(default_factory=list)
    _body_loader: Optional[Callable[[], str]] = None
    _resource_loader: Optional[Callable[[str], str]] = None
    _cached_body: Optional[str] = None

    def tokens_est(self) -> int:
        """Estimate tokens for metadata only."""
        return max(1, len(self.description) // 4)

    def load_body(self) -> str:
        """Load Level 2 body (cached after first call)."""
        if self._cached_body is None and self._body_loader:
            self._cached_body = self._body_loader()
        return self._cached_body or ""

    def load_resource(self, resource_path: str) -> str:
        """Load Level 3 resource on demand."""
        if self._resource_loader:
            return self._resource_loader(resource_path)
        return ""


class ProgressiveDisclosureEngine:
    """Progressive disclosure of skill context.

    Prevents context explosion by loading only metadata at startup,
    body on relevance, and resources on demand.

    Usage:
        engine = ProgressiveDisclosureEngine()
        engine.register_skill("code_review",
            metadata="Reviews code for bugs, style, security",
            keywords=["review", "code", "bugs", "security"],
            body_loader=lambda: open("skills/code_review.md").read())
        meta = engine.get_metadata_all()  # ~100 tokens per skill
        relevant = engine.evaluate_relevance("review my code for bugs")
        body = engine.load_body("code_review")  # <5K tokens
    """

    def __init__(self):
        self._skills: Dict[str, SkillDescriptor] = {}
        self._keyword_index: Dict[str, List[str]] = {}

    def register_skill(self, name: str, metadata: str,
                       keywords: Optional[List[str]] = None,
                       body_loader: Optional[Callable[[], str]] = None,
                       resource_loader: Optional[Callable[[str], str]] = None) -> None:
        """Register a skill at 3 levels."""
        desc = SkillDescriptor(
            name=name,
            description=metadata,
            keywords=keywords or [],
            _body_loader=body_loader,
            _resource_loader=resource_loader,
        )
        self._skills[name] = desc
        # Build inverted index
        for kw in (keywords or []):
            kw_lower = kw.lower()
            if kw_lower not in self._keyword_index:
                self._keyword_index[kw_lower] = []
            self._keyword_index[kw_lower].append(name)

    def get_metadata_all(self) -> List[Dict]:
        """Return all Level 1 metadata (what goes in system prompt)."""
        return [
            {"name": s.name, "description": s.description, "tokens": s.tokens_est()}
            for s in self._skills.values()
        ]

    def evaluate_relevance(self, task_context: str,
                           top_k: int = 5) -> List[Dict]:
        """Keyword scoring to find relevant skills.

        Returns top_k skill descriptors with relevance scores.
        """
        query_words = set(w.lower() for w in task_context.split())
        scores: Dict[str, int] = {}

        for word in query_words:
            for skill_name in self._keyword_index.get(word, []):
                scores[skill_name] = scores.get(skill_name, 0) + 1

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [
            {
                "name": name,
                "score": score,
                "description": self._skills[name].description,
                "tokens_meta": self._skills[name].tokens_est(),
            }
            for name, score in ranked
        ]

    def load_body(self, skill_name: str) -> str:
        """Load Level 2 body for a skill."""
        skill = self._skills.get(skill_name)
        if skill is None:
            return ""
        return skill.load_body()

    def load_resource(self, skill_name: str,
                      resource_path: str) -> str:
        """Load Level 3 resource on demand."""
        skill = self._skills.get(skill_name)
        if skill is None:
            return ""
        return skill.load_resource(resource_path)

    def stats(self) -> Dict:
        """Return counts and token estimates."""
        meta_tokens = sum(s.tokens_est() for s in self._skills.values())
        return {
            "registered_skills": len(self._skills),
            "metadata_tokens_est": meta_tokens,
            "keyword_index_size": len(self._keyword_index),
        }
