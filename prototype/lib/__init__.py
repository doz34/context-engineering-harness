"""CE-Harness POV library."""
from .dsl import parse, parse_multi, emit, validate_brief
from .state import StateDB
from .encrypted_state import EncryptedStateDB
from .token_ledger import TokenLedger
from .subagent_firewall import SubagentFirewall, SubagentBrief, SubagentResult
from .ace_compact import ACECompact, CompactionItem

# v1.1.1: 6 corpus modules wired in (CRIT-3 fix)
from .failure_detector import ContextFailureDetector, Finding, Severity
from .token_economics import TokenEconomicsManager, ModelProfile
from .progressive_disclosure import ProgressiveDisclosureEngine, SkillDescriptor
from .lazy_tool_discovery import ToolDiscoveryEngine, ToolDescriptor
from .verification_framework import (
    VerificationFramework,
    VerificationCheck,
    CheckResult,
    make_file_exists_check,
    make_content_check,
    make_command_check,
    make_regex_check,
)
from .event_driven_memory import EventDrivenMemory, MemoryEvent, MemoryBlock

__all__ = [
    # Core
    "parse", "parse_multi", "emit", "validate_brief",
    "StateDB", "EncryptedStateDB",
    "TokenLedger",
    "SubagentFirewall", "SubagentBrief", "SubagentResult",
    "ACECompact", "CompactionItem",
    # Corpus v1.1.1
    "ContextFailureDetector", "Finding", "Severity",
    "TokenEconomicsManager", "ModelProfile",
    "ProgressiveDisclosureEngine", "SkillDescriptor",
    "ToolDiscoveryEngine", "ToolDescriptor",
    "VerificationFramework", "VerificationCheck", "CheckResult",
    "make_file_exists_check", "make_content_check",
    "make_command_check", "make_regex_check",
    "EventDrivenMemory", "MemoryEvent", "MemoryBlock",
]
