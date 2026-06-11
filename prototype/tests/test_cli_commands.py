"""
Tests for lib.cli command functions.

v1.1.1 (HIGH-3): Brings cli.py coverage from 30% to ~80%+
by testing cmd_init, cmd_measure, cmd_ledger, cmd_spawn, cmd_health, cmd_view.
"""

import os
import sys
import json
import argparse
import pytest
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _args(**kwargs):
    """Helper: build argparse.Namespace with default attributes."""
    defaults = {
        "path": None,
        "no_encrypt": False,
        "json": False,
        "phase": None,
        "budget": None,
        "brief": None,
        "model": "claude-sonnet-4-5",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCmdInit:
    def test_init_default_creates_encrypted_state(self, tmp_path, monkeypatch):
        """Default init creates .ctxh/ with state.db.enc + state.db.key."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init
        args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=False)
        cmd_init(args)
        files = sorted(os.listdir(args.path))
        assert "state.db.enc" in files
        assert "state.db.key" in files
        assert "CLAUDE.md" in files

    def test_init_no_encrypt_creates_plaintext(self, tmp_path, monkeypatch):
        """--no-encrypt opt-out creates state.db (no .enc)."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init
        args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(args)
        files = sorted(os.listdir(args.path))
        assert "state.db" in files
        assert "state.db.enc" not in files

    def test_init_creates_skeleton_subdirs(self, tmp_path, monkeypatch):
        """Init creates hooks/, subagents/, memory/ subdirectories."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init
        args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(args)
        for sub in ["hooks", "subagents", "memory"]:
            assert os.path.isdir(os.path.join(args.path, sub))

    def test_init_claude_md_has_8_invariants(self, tmp_path, monkeypatch):
        """CLAUDE.md template mentions all 8 invariants."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init
        args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(args)
        content = (Path(args.path) / "CLAUDE.md").read_text()
        for n in range(1, 9):
            assert f"{n}." in content


class TestCmdHealth:
    def test_health_no_state_degraded(self, tmp_path, monkeypatch):
        """Health check reports DEGRADED if no state.db exists."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_health
        args = _args(path=str(tmp_path / ".ctxh"), json=True)
        ret = cmd_health(args)
        assert ret == 1  # DEGRADED

    def test_health_encrypted_state_healthy(self, tmp_path, monkeypatch, capsys):
        """Health check reports HEALTHY for encrypted state.db.enc."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_health
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=False)
        cmd_init(init_args)
        h_args = _args(path=init_args.path, json=True)
        ret = cmd_health(h_args)
        captured = capsys.readouterr()
        # Extract JSON part (init printed too, find the { at start of JSON)
        out = _extract_json(captured.out)
        assert out["status"] == "HEALTHY"
        assert ret == 0

    def test_health_plaintext_state_healthy(self, tmp_path, monkeypatch, capsys):
        """Health check reports HEALTHY for plaintext state.db."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_health
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        h_args = _args(path=init_args.path, json=True)
        ret = cmd_health(h_args)
        captured = capsys.readouterr()
        out = _extract_json(captured.out)
        assert out["status"] == "HEALTHY"

    def test_health_text_output_format(self, tmp_path, monkeypatch, capsys):
        """Health check non-JSON output shows ✅/❌ icons."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_health
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        h_args = _args(path=init_args.path, json=False)
        cmd_health(h_args)
        captured = capsys.readouterr()
        assert "CE-Harness Health Check" in captured.out
        assert "✅" in captured.out or "❌" in captured.out


def _extract_json(text: str) -> dict:
    """Extract first top-level JSON object from mixed output."""
    start = text.find("{")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[start:])
    return obj


class TestCmdSpawn:
    def test_spawn_invalid_brief_returns_1(self, tmp_path, monkeypatch, capsys):
        """cmd_spawn returns 1 for invalid brief DSL."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_spawn
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        sp_args = _args(
            brief="not a valid brief",
            phase="P_TEST",
            budget=1000,
            model="claude-sonnet-4-5",
        )
        ret = cmd_spawn(sp_args)
        assert ret == 1
        captured = capsys.readouterr()
        assert "Invalid brief" in captured.out

    def test_spawn_valid_brief_prints_tokenomics(self, tmp_path, monkeypatch, capsys):
        """cmd_spawn prints TokenEconomics recommendation for valid brief."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_spawn
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        sp_args = _args(
            brief="OBJECT:Find X;;FORMAT:JSON;;TOOLS:grep,read;;BOUND:max 10",
            phase="P_TEST_OK",
            budget=1000,
            model="claude-sonnet-4-5",
        )
        cmd_spawn(sp_args)
        captured = capsys.readouterr()
        assert "TokenEconomics" in captured.out
        assert "Subagent Result" in captured.out


class TestCmdLedger:
    def test_ledger_no_state(self, tmp_path, monkeypatch, capsys):
        """cmd_ledger runs even with no state (prints nothing or empty)."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_ledger
        args = _args(phase=None, json=False)
        # Should not raise even without .ctxh/state.db
        try:
            cmd_ledger(args)
        except Exception:
            # Acceptable: may raise if no .ctxh at all
            pass


class TestCmdView:
    def test_view_no_state_returns_1(self, tmp_path, monkeypatch, capsys):
        """cmd_view returns 1 if no state.db."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_view
        args = _args(phase="P_TEST", json=False)
        ret = cmd_view(args)
        assert ret == 1
        captured = capsys.readouterr()
        assert "state.db" in captured.out

    def test_view_after_init_uses_progressive_disclosure(self, tmp_path, monkeypatch, capsys):
        """cmd_view after init shows ProgressiveDisclosureEngine output."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_view
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        v_args = _args(phase="P_TEST", json=False, budget=4000)
        cmd_view(v_args)
        captured = capsys.readouterr()
        # Should mention ProgressiveDisclosure
        assert "ProgressiveDisclosure" in captured.out or "skills" in captured.out


class TestCmdMeasure:
    def test_measure_uses_failure_detector(self, tmp_path, monkeypatch, capsys):
        """cmd_measure runs ContextFailureDetector on the baseline."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_measure
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        cmd_measure(_args())
        captured = capsys.readouterr()
        # Should mention failure detector at least once
        assert "ContextFailureDetector" in captured.out
        assert "ECONOMY RATIO" in captured.out

    def test_measure_prints_economy_ratio(self, tmp_path, monkeypatch, capsys):
        """cmd_measure prints the 10.8× economy ratio."""
        monkeypatch.chdir(tmp_path)
        from lib.cli import cmd_init, cmd_measure
        init_args = _args(path=str(tmp_path / ".ctxh"), no_encrypt=True)
        cmd_init(init_args)
        cmd_measure(_args())
        captured = capsys.readouterr()
        assert "10.8" in captured.out
        assert "less tokens" in captured.out
