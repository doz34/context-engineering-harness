#!/usr/bin/env python3
"""
CE-Harness CLI
==============
Context Engineering Harness — opinionated open-source harness for LLM agents.
"""

import sys
import argparse
import json
import os
import datetime
import signal
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import StateDB, TokenLedger, SubagentFirewall, SubagentBrief
from lib.hooks import HookSystem, HookEvent, HookContext, HookResult, HookDecision
from lib.pii_tokenizer import get_tokenizer as _pii_tokenizer


def cmd_init(args):
    """Initialize a new .ctxh/ directory in current path."""
    target = args.path or ".ctxh"
    os.makedirs(target, exist_ok=True)

    # Create state DB
    state = StateDB(path=os.path.join(target, "state.db"))

    # Create skeleton
    for sub in ["hooks", "subagents", "memory"]:
        os.makedirs(os.path.join(target, sub), exist_ok=True)

    # Create CLAUDE.md template
    claude_md = f"""# {Path.cwd().name} — CE-Harness v1.1

## Identity
- Harness: CE-Harness v1.1 (Production-Ready)
- Initialized: {datetime.datetime.now().isoformat()}

## 8 Invariants (enforced)
1. Token budget per phase (60/70/85/95% triggers)
2. Code-as-API (not tool calling)
3. Subagent firewall (isolated contexts)
4. Compaction ACE-style (preserve events)
5. Layout head/tail (lost-in-the-middle)
6. Adversarial gates (T1/T2/T3 + Drew 4-modes)
7. Pre-hydrate per phase
8. Self-improving playbook (ACE)

## Phase conventions
- Use 35-min budget hard cap (Morph 2026 wall)
- Use subagent firewall for any parallel work
- Pre-hydrate at phase start

## Don'ts
- No tool result retaining (auto-clear via PostToolUse)
- No peer-to-peer subagent channels
- No 50+ subagents for simple tasks
- No CLAUDE.md > 60 lines (HumanLayer 2026)
"""
    with open(os.path.join(target, "CLAUDE.md"), "w") as f:
        f.write(claude_md)

    print(f"✅ CE-Harness initialized in {target}/")
    print(f"   - state.db (SQLite WAL)")
    print(f"   - CLAUDE.md (60-line template)")
    print(f"   - hooks/ subagents/ memory/")


def cmd_measure(args):
    """Run a measurement demo: baseline vs with-harness tokens."""
    print("=" * 60)
    print("CE-Harness — Measurement Demo")
    print("=" * 60)

    # Clean state for repeatable demo
    db_path = ".ctxh/state.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    state = StateDB(path=db_path)
    ledger = TokenLedger(state=state, verbose=True)

    # Simulate 1 phase: search "parse_query" in a codebase
    phase_id = "P_DEMO_SEARCH"
    ledger.start_phase(phase_id, "Demo Search", soft_cap=8000, hard_cap=15000)

    print("\n--- BASELINE: 1 agent loads everything ---")
    # Baseline: agent reads all files
    ledger.record(phase_id, "messages", "input", 50000,
                  model="claude-opus-4-8",
                  metadata={"scenario": "baseline_naive"})
    ledger.record(phase_id, "output", "output", 3000,
                  model="claude-opus-4-8")

    print(f"\n📊 Baseline total: {state.phase_total(phase_id):,} tokens")

    # Reset for next scenario
    ledger.end_phase(phase_id, "aborted")
    phase_id_2 = "P_DEMO_FIREWALL"
    ledger.start_phase(phase_id_2, "Demo Search (firewall)", soft_cap=8000, hard_cap=15000)

    print("\n--- WITH CE-HARNESS: subagent firewall ---")
    # With harness: lead agent + subagent firewall
    ledger.record(phase_id_2, "messages", "input", 200,
                  model="claude-opus-4-8", agent="lead",
                  metadata={"scenario": "brief_to_subagent"})

    # Subagent does the heavy lifting
    ledger.record(phase_id_2, "subagent_context", "input", 4000,
                  model="claude-sonnet-4-5", agent="subagent_1",
                  metadata={"scenario": "isolated_search"})

    # Subagent returns summary
    ledger.record(phase_id_2, "messages", "input", 200,
                  model="claude-sonnet-4-5", agent="subagent_1",
                  metadata={"scenario": "summary_return"})

    ledger.record(phase_id_2, "output", "output", 500,
                  model="claude-opus-4-8")

    print(f"\n📊 With firewall total: {state.phase_total(phase_id_2):,} tokens")
    baseline = 50000 + 3000
    firewall = 200 + 4000 + 200 + 500
    print(f"\n🎯 ECONOMY RATIO: {baseline:,} → {firewall:,} = {baseline/firewall:.1f}× less tokens")

    try:
        from lib.hooks import HookSystem, HookEvent, HookContext
        _hs = HookSystem()
        _hs.fire(HookContext(event=HookEvent.PHASE_END, payload={
            "phase_id": phase_id_2, "tokens": state.phase_total(phase_id_2),
        }))
    except Exception as e:
        print(f"hook system warning: {e}", file=sys.stderr)

    print("\n" + "=" * 60)
    print("Phase dashboard (with firewall):")
    print("=" * 60)
    print(ledger.dashboard(phase_id_2))


def cmd_ledger(args):
    """Show token ledger."""
    state = StateDB(path=".ctxh/state.db")
    ledger = TokenLedger(state=state, verbose=False)

    if args.phase:
        print(ledger.dashboard(args.phase))
    else:
        with state.conn() as c:
            phases = c.execute(
                "SELECT id, name, tokens_used, budget_soft_cap, budget_hard_cap, status "
                "FROM phase ORDER BY started_at"
            ).fetchall()
            for ph in phases:
                pid, name, used, soft, hard, status = ph
                pct = (used / soft * 100) if soft else 0
                print(f"  {pid:20} {name:30} {used:>6,}/{soft:>6,} ({pct:>5.1f}%) {status}")


def cmd_spawn(args):
    """Spawn a subagent with brief validation."""
    brief = SubagentBrief.from_dsl(args.brief)
    valid, errors = brief.validate()
    if not valid:
        print(f"❌ Invalid brief: {errors}")
        return 1

    state = StateDB(path=".ctxh/state.db")
    ledger = TokenLedger(state=state, verbose=True)
    # End any prior phase with same id
    with state.conn() as c:
        c.execute("UPDATE phase SET ended_at = datetime('now'), status = 'complete' "
                  "WHERE id = ? AND ended_at IS NULL", (args.phase,))
    ledger.start_phase(args.phase, "Subagent demo", soft_cap=8000, hard_cap=15000)

    firewall = SubagentFirewall(ledger, args.phase)
    from lib.hooks import HookSystem, HookEvent, HookContext
    _hs = HookSystem()
    try:
        _used = state.phase_total(args.phase)
        _soft, _hard = state.phase_budget(args.phase)
        _remaining = (_hard - _used) if _hard else args.budget
    except Exception:
        _remaining = args.budget
    _pre = _hs.fire(HookContext(event=HookEvent.PRE_TOOL_USE, payload={
        "tool_name": "subagent_spawn",
        "phase_id": args.phase,
        "brief": brief.to_dsl(),
        "budget": args.budget,
        "budget_remaining": _remaining,
    }))
    if _pre.decision == HookDecision.DENY:
        print(f"❌ Spawn denied by PreToolUse hook: {_pre.reason}")
        return 1

    result = firewall.spawn(brief, context_budget=args.budget, model=args.model)

    _post = _hs.fire(HookContext(event=HookEvent.POST_TOOL_USE, payload={
        "tool_name": "subagent_spawn",
        "phase_id": args.phase,
        "result": result.to_dsl(),
    }))

    print("\n📋 Subagent Result:")
    if _post.decision == HookDecision.MODIFY and "tool_result" in (_post.modified_payload or {}):
        print(_post.modified_payload["tool_result"])
    else:
        print(result.to_dsl())
    print(f"\n🛡️  Compression: {result.compression_ratio():.1f}× vs raw dump")
    print(f"🔒 Isolation: {firewall.verify_isolation(firewall.last_sub_id)}")


def cmd_health(args):
    """Verify CE-Harness infrastructure integrity (v1.1)."""
    checks = {}
    base_path = args.path or ".ctxh"

    # 1. State DB integrity
    db_path = os.path.join(base_path, "state.db")
    if os.path.exists(db_path):
        try:
            state = StateDB(path=db_path)
            with state.conn() as c:
                tables = {r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}
            checks["state_db_schema"] = {"ok": len(tables) >= 4, "tables": len(tables)}
            # WAL integrity
            with state.conn() as c:
                integrity = c.execute("PRAGMA integrity_check").fetchone()
            checks["state_db_integrity"] = {"ok": integrity[0] == "ok"}

            # Audit chain
            chain = state.verify_audit_chain()
            checks["audit_chain"] = {
                "ok": chain.get("ok", False),
                "checked": chain.get("checked", 0),
            }
        except Exception as e:
            checks["state_db"] = {"ok": False, "reason": str(e)}
    else:
        checks["state_db"] = {"ok": False, "reason": "not found (run ctxh init)"}

    # 2. Encryption status
    enc_path = db_path + ".enc"
    checks["encryption"] = {
        "ok": True,
        "encrypted": os.path.exists(enc_path),
        "note": "encrypted at rest" if os.path.exists(enc_path) else "plaintext (set CTXH_ENCRYPTED=1)",
    }

    # 3. PII salt
    salt_path = os.path.join(base_path, "pii.salt")
    salt_exists = os.path.exists(salt_path)
    checks["pii_salt"] = {
        "ok": True,  # not having a salt is fine (auto-generated on first use)
        "persisted": salt_exists,
        "note": "deterministic tokens" if salt_exists else "auto-generated per run (not yet persisted)",
    }

    # 4. Disk space (warn if < 100MB)
    try:
        disk_dir = os.path.dirname(db_path) or "."
        if not os.path.isdir(disk_dir):
            disk_dir = "."
        stat = os.statvfs(disk_dir)
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        checks["disk_space_mb"] = {
            "ok": free_mb > 100,
            "free_mb": round(free_mb, 1),
        }
    except (AttributeError, OSError):
        checks["disk_space_mb"] = {"ok": True, "note": "check skipped (unsupported platform)"}

    # 5. Logging
    log_level = os.environ.get("CTXH_LOG_LEVEL", "not set (default: WARNING)")
    checks["logging"] = {
        "ok": True,
        "level": log_level,
        "format": os.environ.get("CTXH_LOG_FORMAT", "json (default)"),
    }

    all_ok = all(c.get("ok", False) for c in checks.values())

    if getattr(args, "json", False):
        print(json.dumps({
            "status": "HEALTHY" if all_ok else "DEGRADED",
            "version": "1.1.0",
            "checks": checks,
        }, indent=2))
    else:
        print(f"CE-Harness Health Check — {'✅ HEALTHY' if all_ok else '❌ DEGRADED'}")
        print("-" * 50)
        for name, result in checks.items():
            icon = "✅" if result.get("ok") else "❌"
            detail = ", ".join(f"{k}={v}" for k, v in result.items() if k != "ok")
            print(f"  {icon} {name}: {detail}")

    return 0 if all_ok else 1


def cmd_view(args):
    """Build and display the curated LLM view for a phase (v1.1)."""
    from lib.llm_view import LLMViewBuilder

    db_path = ".ctxh/state.db"
    if not os.path.exists(db_path):
        print("❌ No state.db found. Run `ctxh init` first.")
        return 1

    state = StateDB(path=db_path)
    budget = args.budget or 4000
    builder = LLMViewBuilder(state=state, phase_id=args.phase, budget=budget)

    # Add budget status from state
    builder.add_budget_status()

    # Add gate state from audit chain
    chain = state.verify_audit_chain()
    builder.add_gate_state({"audit_chain": chain})

    # Build the view
    view = builder.build()
    report = builder.section_report()

    if getattr(args, "json", False):
        print(json.dumps({"view": view, "report": report}, indent=2))
    else:
        print(view)
        print(f"\n_Report: {report['total_tokens_est']} est tokens, "
              f"{report['budget_utilization']}% utilization_")


def main():
    parser = argparse.ArgumentParser(
        prog="ctxh",
        description="CE-Harness — Context Engineering Harness for LLM agents",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize CE-Harness in current dir")
    p_init.add_argument("--path", default=None)
    p_init.set_defaults(func=cmd_init)

    # measure
    p_measure = subparsers.add_parser("measure", help="Run measurement demo")
    p_measure.set_defaults(func=cmd_measure)

    # ledger
    p_ledger = subparsers.add_parser("ledger", help="Show token ledger")
    p_ledger.add_argument("--phase", default=None)
    p_ledger.set_defaults(func=cmd_ledger)

    # spawn
    p_spawn = subparsers.add_parser("spawn", help="Spawn subagent with brief")
    p_spawn.add_argument("--brief", required=True)
    p_spawn.add_argument("--phase", default="P_DEMO")
    p_spawn.add_argument("--budget", type=int, default=4000)
    p_spawn.add_argument("--model", default="claude-sonnet-4-5")
    p_spawn.set_defaults(func=cmd_spawn)

    # health (v1.1)
    p_health = subparsers.add_parser("health", help="Check CE-Harness infrastructure")
    p_health.add_argument("--path", default=None)
    p_health.add_argument("--json", action="store_true", help="JSON output")
    p_health.set_defaults(func=cmd_health)

    # view (v1.1)
    p_view = subparsers.add_parser("view", help="Show curated LLM view for a phase")
    p_view.add_argument("phase", help="Phase ID to view")
    p_view.add_argument("--budget", type=int, default=None, help="Token budget")
    p_view.add_argument("--json", action="store_true", help="JSON output")
    p_view.set_defaults(func=cmd_view)

    args = parser.parse_args()

    # v1.1: Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)

    # Verify audit chain on existing DB
    _audit_check_path = os.path.join(
        getattr(args, "path", None) or ".ctxh", "state.db"
    )
    if args.cmd not in ("init", "health") and os.path.exists(_audit_check_path):
        try:
            _st = StateDB(path=_audit_check_path)
            _result = _st.verify_audit_chain()
            if not _result.get("ok"):
                print(
                    f"⚠️  Audit chain FAILED: "
                    f"{_result.get('reason')} (id={_result.get('first_invalid_id')})"
                )
            elif _result.get("checked", 0) > 0:
                print(
                    f"🔍 Audit chain OK ({_result['checked']} events, "
                    f"epoch={_result.get('epoch_id', '?')})"
                )
        except Exception as e:
            print(f"⚠️  Audit chain check errored: {e}")

    args.func(args)


# --- Signal handlers ---
_active_state_db = None


def _graceful_shutdown(signum, frame):
    """SIGTERM/SIGINT handler: flush state DB, exit cleanly (v1.1)."""
    global _active_state_db
    if _active_state_db is not None:
        try:
            with _active_state_db.conn() as c:
                c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
    sys.exit(128 + signum)


if __name__ == "__main__":
    main()
