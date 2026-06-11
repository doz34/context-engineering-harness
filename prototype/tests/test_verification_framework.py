"""Tests for verification_framework.py — deterministic gather→act→verify loop."""

import os
import tempfile
import unittest

from lib.verification_framework import (
    VerificationFramework,
    make_command_check,
    make_content_check,
    make_file_exists_check,
    make_regex_check,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROTOTYPE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_framework() -> VerificationFramework:
    """Return a fresh framework with default max_iterations."""
    return VerificationFramework(max_iterations=8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAddAndRunCheck(unittest.TestCase):
    """add_check + run_check_by_name round-trip."""

    def test_add_and_run_single_check(self):
        vf = _make_framework()
        vf.add_check(
            "always_ok",
            "deterministic",
            lambda: (True, "looks good"),
            severity="HIGH",
        )
        result = vf.run_check_by_name("always_ok")
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "looks good")
        self.assertEqual(result.severity, "HIGH")

    def test_unknown_check_raises(self):
        vf = _make_framework()
        with self.assertRaises(KeyError):
            vf.run_check_by_name("nonexistent")

    def test_bad_check_type_raises(self):
        vf = _make_framework()
        with self.assertRaises(ValueError):
            vf.add_check("bad", "telepathic", lambda: (True, "nope"))

    def test_bad_severity_raises(self):
        vf = _make_framework()
        with self.assertRaises(ValueError):
            vf.add_check("bad", "deterministic", lambda: (True, "nope"), severity="URGENT")


class TestRunChecksAllPass(unittest.TestCase):
    """run_checks returns all_passed=True when every check succeeds."""

    def test_all_pass(self):
        vf = _make_framework()
        vf.add_check("c1", "deterministic", lambda: (True, "ok"))
        vf.add_check("c2", "deterministic", lambda: (True, "ok"))
        all_passed, results = vf.run_checks()
        self.assertTrue(all_passed)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.passed for r in results))

    def test_empty_framework_passes(self):
        vf = _make_framework()
        all_passed, results = vf.run_checks()
        self.assertTrue(all_passed)
        self.assertEqual(len(results), 0)


class TestRunChecksSomeFail(unittest.TestCase):
    """run_checks returns all_passed=False when any check fails."""

    def test_mixed_results(self):
        vf = _make_framework()
        vf.add_check("pass", "deterministic", lambda: (True, "good"))
        vf.add_check("fail", "deterministic", lambda: (False, "bad"))
        all_passed, results = vf.run_checks()
        self.assertFalse(all_passed)
        self.assertEqual(len(results), 2)
        passed_names = [r.name for r in results if r.passed]
        failed_names = [r.name for r in results if not r.passed]
        self.assertEqual(passed_names, ["pass"])
        self.assertEqual(failed_names, ["fail"])

    def test_exception_treated_as_failure(self):
        vf = _make_framework()

        def _boom():
            raise RuntimeError("kaboom")

        vf.add_check("boom", "deterministic", _boom)
        all_passed, results = vf.run_checks()
        self.assertFalse(all_passed)
        self.assertIn("EXCEPTION", results[0].message)


class TestRunLoopConverges(unittest.TestCase):
    """run_loop calls action_fn and retries until checks pass."""

    def test_converges_after_fix(self):
        vf = _make_framework()
        state = {"fixed": False}

        def flaky_check():
            if state["fixed"]:
                return (True, "fixed")
            return (False, "not yet")

        vf.add_check("flaky", "deterministic", flaky_check)

        def action(round_num, failed):
            state["fixed"] = True

        success, rounds, history = vf.run_loop(action)
        self.assertTrue(success)
        self.assertLessEqual(rounds, 4)
        self.assertGreater(len(history), 1)

    def test_immediate_pass(self):
        vf = _make_framework()
        vf.add_check("ok", "deterministic", lambda: (True, "done"))

        success, rounds, history = vf.run_loop(lambda r, f: None)
        self.assertTrue(success)
        self.assertEqual(rounds, 1)


class TestRunLoopCircuitBreaker(unittest.TestCase):
    """run_loop stops after max_rounds even if checks still fail."""

    def test_circuit_breaker_fires(self):
        vf = VerificationFramework(max_iterations=3)
        vf.add_check("never", "deterministic", lambda: (False, "nope"))
        call_count = {"n": 0}

        def action(round_num, failed):
            call_count["n"] += 1

        success, rounds, history = vf.run_loop(action)
        self.assertFalse(success)
        self.assertLessEqual(rounds, 4)  # initial + 3 actions + final
        self.assertEqual(call_count["n"], 3)  # action called once per failed round

    def test_custom_max_rounds(self):
        vf = VerificationFramework(max_iterations=100)
        vf.add_check("never", "deterministic", lambda: (False, "nope"))

        success, rounds, _ = vf.run_loop(lambda r, f: None, max_rounds=2)
        self.assertFalse(success)


class TestPrebuiltFileExistsCheck(unittest.TestCase):
    """make_file_exists_check factory."""

    def test_file_exists(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            try:
                chk = make_file_exists_check(tmp.name)
                passed, msg = chk.check_fn()
                self.assertTrue(passed)
                self.assertIn(tmp.name, msg)
            finally:
                os.unlink(tmp.name)

    def test_file_missing(self):
        chk = make_file_exists_check("/tmp/__vf_no_such_file_xyz__")
        passed, msg = chk.check_fn()
        self.assertFalse(passed)
        self.assertIn("missing", msg)


class TestPrebuiltContentCheck(unittest.TestCase):
    """make_content_check factory."""

    def test_all_strings_present(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("hello world\nfoo bar baz\n")
            tmp.flush()
            try:
                chk = make_content_check(tmp.name, ["hello", "foo bar"])
                passed, msg = chk.check_fn()
                self.assertTrue(passed)
            finally:
                os.unlink(tmp.name)

    def test_missing_string(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("short content\n")
            tmp.flush()
            try:
                chk = make_content_check(tmp.name, ["short", "MISSING"])
                passed, msg = chk.check_fn()
                self.assertFalse(passed)
                self.assertIn("MISSING", msg)
            finally:
                os.unlink(tmp.name)

    def test_file_not_found(self):
        chk = make_content_check("/tmp/__vf_gone__", ["x"])
        passed, _ = chk.check_fn()
        self.assertFalse(passed)


class TestPrebuiltCommandCheck(unittest.TestCase):
    """make_command_check factory."""

    def test_successful_command(self):
        chk = make_command_check("true")
        passed, msg = chk.check_fn()
        self.assertTrue(passed)

    def test_failing_command(self):
        chk = make_command_check("false", expected_exit_code=1)
        passed, msg = chk.check_fn()
        self.assertTrue(passed)

    def test_unexpected_exit_code(self):
        chk = make_command_check("false")
        passed, msg = chk.check_fn()
        self.assertFalse(passed)
        self.assertIn("expected 0", msg)


class TestSummary(unittest.TestCase):
    """summary() returns structured state."""

    def test_summary_structure(self):
        vf = _make_framework()
        vf.add_check("s1", "deterministic", lambda: (True, "ok"), severity="CRIT")
        vf.run_checks()
        s = vf.summary()
        self.assertIn("s1", s["checks_registered"])
        self.assertEqual(len(s["last_results"]), 1)
        self.assertTrue(s["last_results"][0]["passed"])


if __name__ == "__main__":
    unittest.main()
