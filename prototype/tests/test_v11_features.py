"""
Tests for v1.1 features: EncryptedStateDB, LLMViewBuilder, Observability, CLI commands.
"""

import os
import sys
import json
import tempfile
import shutil
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# === EncryptedStateDB Tests ===

class TestEncryptedStateDB:
    def test_encrypted_state_roundtrip(self, tmp_path):
        """Write data, close, reopen — data survives encryption cycle."""
        from lib.encrypted_state import EncryptedStateDB
        db_path = str(tmp_path / "state.db")
        passphrase = "test-passphrase-v11"

        # Create and write
        esdb = EncryptedStateDB(path=db_path, passphrase=passphrase)
        with esdb.conn() as c:
            c.execute("CREATE TABLE t (id INTEGER, val TEXT)")
            c.execute("INSERT INTO t VALUES (1, 'hello encryption')")
        esdb.close()

        # Verify encrypted file exists
        assert os.path.exists(db_path + ".enc")

        # Reopen and verify
        esdb2 = EncryptedStateDB(path=db_path, passphrase=passphrase)
        with esdb2.conn() as c:
            row = c.execute("SELECT val FROM t WHERE id = 1").fetchone()
        assert row[0] == "hello encryption"
        esdb2.close()

    def test_encrypted_file_not_plaintext(self, tmp_path):
        """The .enc file should not be a valid SQLite file."""
        from lib.encrypted_state import EncryptedStateDB
        db_path = str(tmp_path / "state.db")

        esdb = EncryptedStateDB(path=db_path, passphrase="secret123")
        with esdb.conn() as c:
            c.execute("CREATE TABLE t (x TEXT)")
            c.execute("INSERT INTO t VALUES ('sensitive_data')")
        esdb.close()

        enc_path = db_path + ".enc"
        assert os.path.exists(enc_path)
        with open(enc_path, "rb") as f:
            header = f.read(16)
        # SQLite files start with "SQLite format 3\000"
        assert not header.startswith(b"SQLite format 3")

    def test_encrypted_state_wrong_passphrase_fails(self, tmp_path):
        """Wrong passphrase should fail to decrypt."""
        from lib.encrypted_state import EncryptedStateDB
        db_path = str(tmp_path / "state.db")

        esdb = EncryptedStateDB(path=db_path, passphrase="correct")
        with esdb.conn() as c:
            c.execute("CREATE TABLE t (x TEXT)")
        esdb.close()

        with pytest.raises(Exception):
            EncryptedStateDB(path=db_path, passphrase="wrong")

    def test_encryption_status(self, tmp_path):
        """encryption_status reports correct metadata."""
        from lib.encrypted_state import EncryptedStateDB
        db_path = str(tmp_path / "state.db")

        esdb = EncryptedStateDB(path=db_path, passphrase="test")
        status = esdb.encryption_status
        assert "cipher" in status
        assert "enc_path" in status
        esdb.close()
        # After close, encrypted_at_rest should be True
        assert esdb.is_encrypted_at_rest()


# === LLMViewBuilder Tests ===

class TestLLMViewBuilder:
    def test_head_contains_budget(self):
        """Budget status appears in head section."""
        from lib.llm_view import LLMViewBuilder
        builder = LLMViewBuilder(budget=4000)
        builder.add_section("test", 1, "head content")
        view = builder.build()
        assert "head content" in view

    def test_tail_contains_findings(self):
        """Adversarial findings appear in tail section."""
        from lib.llm_view import LLMViewBuilder
        builder = LLMViewBuilder(phase_id="P5", budget=4000)
        builder.add_adversarial_findings(["potential injection detected"])
        view = builder.build()
        assert "potential injection detected" in view
        assert "Adversarial Findings" in view

    def test_middle_is_compacted(self):
        """Working context in middle is compacted under budget."""
        from lib.llm_view import LLMViewBuilder
        from lib.ace_compact import CompactionItem
        items = [
            CompactionItem(kind="tool_result", content=f"result {i} " * 100)
            for i in range(50)
        ]
        builder = LLMViewBuilder(budget=2000)
        builder.add_working_context(items)
        view = builder.build()
        assert len(view) < 50000  # Compacted, not raw 50 items

    def test_head_tail_preserved(self):
        """Head and tail survive even when total content is large."""
        from lib.llm_view import LLMViewBuilder
        builder = LLMViewBuilder(budget=1000)
        builder.add_section("critical_gate", 1, "MUST SEE THIS")
        builder.add_section("finding", 3, "CRITICAL FINDING AT END")
        builder.add_section("middle_fluff", 2, "x" * 50000)
        view = builder.build()
        assert "MUST SEE THIS" in view
        assert "CRITICAL FINDING AT END" in view

    def test_empty_build_returns_minimal(self):
        """No sections produces a valid empty view."""
        from lib.llm_view import LLMViewBuilder
        builder = LLMViewBuilder(phase_id="P0", budget=4000)
        view = builder.build()
        assert "P0" in view
        assert "no sections" in view

    def test_section_report_accuracy(self):
        """Section report has correct counts."""
        from lib.llm_view import LLMViewBuilder
        builder = LLMViewBuilder(phase_id="P5", budget=4000)
        builder.add_section("h1", 1, "head")
        builder.add_section("m1", 2, "middle")
        builder.add_section("t1", 3, "tail")
        report = builder.section_report()
        assert len(report["sections"]) == 3
        assert report["budget"] == 4000


# === Observability Tests ===

class TestObservability:
    def test_json_formatter_output(self):
        """JSON formatter produces valid JSON with required keys."""
        from lib.observability import JSONFormatter
        import logging
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="ctxh", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "ts" in data
        assert "level" in data
        assert "msg" in data
        assert data["level"] == "INFO"
        assert data["msg"] == "test message"

    def test_get_logger_returns_logger(self):
        """get_logger returns a configured logger."""
        from lib.observability import get_logger
        logger = get_logger("test_ctxh")
        assert logger is not None
        assert logger.name == "test_ctxh"

    def test_log_level_from_env(self, monkeypatch):
        """CTXH_LOG_LEVEL env var controls log level."""
        from lib.observability import get_logger, _configured_loggers
        import logging
        _configured_loggers.discard("test_env_level")
        monkeypatch.setenv("CTXH_LOG_LEVEL", "DEBUG")
        logger = get_logger("test_env_level")
        assert logger.level == logging.DEBUG

    def test_text_formatter(self):
        """Text formatter produces human-readable output."""
        from lib.observability import TextFormatter
        import logging
        formatter = TextFormatter(color=False)
        record = logging.LogRecord(
            name="ctxh", level=logging.WARNING, pathname="", lineno=0,
            msg="test warning", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "WARNING" in output
        assert "test warning" in output

    def test_log_event_with_extra(self):
        """log_event attaches extra fields."""
        from lib.observability import get_logger, log_event, _configured_loggers
        import logging, io
        _configured_loggers.discard("test_extra")
        logger = get_logger("test_extra")
        logger.setLevel(logging.DEBUG)
        # Capture output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from lib.observability import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.handlers = [handler]
        log_event(logger, "INFO", "hello", phase="P5", tokens=4200)
        output = stream.getvalue()
        data = json.loads(output.strip())
        assert data["phase"] == "P5"
        assert data["tokens"] == 4200


# === Health Check Tests ===

class TestHealthCheck:
    def test_health_no_state_db(self, tmp_path):
        """Health check reports missing state.db gracefully."""
        from lib.cli import cmd_health
        args = argparse.Namespace(path=str(tmp_path / "nonexistent"), json=True)
        ret = cmd_health(args)
        # Missing DB = DEGRADED
        assert ret == 1

    def test_health_with_init(self, tmp_path):
        """After init, health should be HEALTHY."""
        import os
        from lib.cli import cmd_init, cmd_health
        # Ensure cwd is valid (other tests' tmp_path cleanup may invalidate it)
        try:
            os.getcwd()
        except FileNotFoundError:
            os.chdir("/tmp")
        init_path = str(tmp_path / "ctxh_test")
        args = argparse.Namespace(path=init_path)
        cmd_init(args)
        args_h = argparse.Namespace(path=init_path, json=True)
        ret = cmd_health(args_h)
        assert ret == 0


import argparse
