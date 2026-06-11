"""Deterministic Verification Framework — gather → act → verify loop.

Implements deterministic pass/fail checks with a circuit-breaker loop
that runs action→verify cycles until all checks pass or max rounds exhausted.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

CheckFn = Callable[[], tuple[bool, str]]


@dataclass
class VerificationCheck:
    """A single verification check with deterministic pass/fail semantics."""

    name: str
    check_type: str  # "deterministic" | "visual" | "evaluator"
    check_fn: CheckFn
    severity: str = "MED"  # LOW | MED | HIGH | CRIT


@dataclass
class CheckResult:
    """Outcome of a single check execution."""

    name: str
    check_type: str
    severity: str
    passed: bool
    message: str


class VerificationFramework:
    """Orchestrates the gather → act → verify loop."""

    def __init__(self, max_iterations: int = 8) -> None:
        self._checks: dict[str, VerificationCheck] = {}
        self._last_results: list[CheckResult] = []
        self._max_iterations = max_iterations

    # ── registry ──────────────────────────────────────────────────────

    def add_check(
        self,
        name: str,
        check_type: str,
        check_fn: CheckFn,
        severity: str = "MED",
    ) -> None:
        if check_type not in ("deterministic", "visual", "evaluator"):
            raise ValueError(f"Unknown check_type: {check_type!r}")
        if severity not in ("LOW", "MED", "HIGH", "CRIT"):
            raise ValueError(f"Unknown severity: {severity!r}")
        self._checks[name] = VerificationCheck(
            name=name,
            check_type=check_type,
            check_fn=check_fn,
            severity=severity,
        )

    # ── execution ─────────────────────────────────────────────────────

    def run_checks(self) -> tuple[bool, list[CheckResult]]:
        """Run every registered check. Returns (all_passed, results)."""
        results: list[CheckResult] = []
        for chk in self._checks.values():
            try:
                passed, message = chk.check_fn()
            except Exception as exc:  # noqa: BLE001
                passed, message = False, f"EXCEPTION: {exc}"
            results.append(
                CheckResult(
                    name=chk.name,
                    check_type=chk.check_type,
                    severity=chk.severity,
                    passed=passed,
                    message=message,
                )
            )
        self._last_results = results
        all_passed = all(r.passed for r in results) if results else True
        return all_passed, results

    def run_check_by_name(self, name: str) -> CheckResult:
        """Run a single named check. Raises KeyError if unknown."""
        chk = self._checks[name]
        try:
            passed, message = chk.check_fn()
        except Exception as exc:  # noqa: BLE001
            passed, message = False, f"EXCEPTION: {exc}"
        result = CheckResult(
            name=chk.name,
            check_type=chk.check_type,
            severity=chk.severity,
            passed=passed,
            message=message,
        )
        self._last_results = [result]
        return result

    # ── loop ──────────────────────────────────────────────────────────

    def run_loop(
        self,
        action_fn: Callable[[int, list[CheckResult]], None],
        max_rounds: Optional[int] = None,
    ) -> tuple[bool, int, list[list[CheckResult]]]:
        """Run action→verify loop until all checks pass or circuit breaks.

        Args:
            action_fn: receives (round_number, failed_checks). Should fix
                       the issues so the next verification round passes.
            max_rounds: override per-loop cap (defaults to __init__ value).

        Returns:
            (success, rounds_used, results_history)
        """
        cap = max_rounds if max_rounds is not None else self._max_iterations
        history: list[list[CheckResult]] = []

        for round_num in range(1, cap + 1):
            all_passed, results = self.run_checks()
            history.append(results)
            if all_passed:
                return True, round_num, history
            failed = [r for r in results if not r.passed]
            action_fn(round_num, failed)

        # Final verification after last action
        all_passed, results = self.run_checks()
        history.append(results)
        return all_passed, len(history), history

    # ── introspection ─────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return registry info and last run results."""
        return {
            "checks_registered": list(self._checks.keys()),
            "last_results": [
                {
                    "name": r.name,
                    "type": r.check_type,
                    "severity": r.severity,
                    "passed": r.passed,
                    "message": r.message,
                }
                for r in self._last_results
            ],
        }


# ── Pre-built check factories ─────────────────────────────────────────


def make_file_exists_check(path: str, severity: str = "MED") -> VerificationCheck:
    """Factory: verify a file exists on disk."""

    def _check() -> tuple[bool, str]:
        if os.path.isfile(path):
            return True, f"File exists: {path}"
        return False, f"File missing: {path}"

    return VerificationCheck(
        name=f"file_exists:{path}",
        check_type="deterministic",
        check_fn=_check,
        severity=severity,
    )


def make_content_check(
    path: str,
    required_strings: list[str],
    severity: str = "MED",
) -> VerificationCheck:
    """Factory: verify a file contains all required strings."""

    def _check() -> tuple[bool, str]:
        if not os.path.isfile(path):
            return False, f"File missing: {path}"
        content = open(path).read()  # noqa: SIM115
        missing = [s for s in required_strings if s not in content]
        if not missing:
            return True, f"All {len(required_strings)} strings found in {path}"
        return False, f"Missing strings in {path}: {missing!r}"

    return VerificationCheck(
        name=f"content:{path}",
        check_type="deterministic",
        check_fn=_check,
        severity=severity,
    )


def make_command_check(
    command: str,
    expected_exit_code: int = 0,
    severity: str = "MED",
) -> VerificationCheck:
    """Factory: verify a shell command returns the expected exit code."""

    def _check() -> tuple[bool, str]:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == expected_exit_code:
            return True, f"Command exited {proc.returncode}: {command}"
        return False, (
            f"Command exited {proc.returncode} (expected {expected_exit_code}): "
            f"{command}\nstderr: {proc.stderr[:200]}"
        )

    return VerificationCheck(
        name=f"command:{command}",
        check_type="deterministic",
        check_fn=_check,
        severity=severity,
    )


def make_regex_check(
    path: str,
    pattern: str,
    severity: str = "MED",
) -> VerificationCheck:
    """Factory: verify a file matches a regex pattern."""

    def _check() -> tuple[bool, str]:
        if not os.path.isfile(path):
            return False, f"File missing: {path}"
        content = open(path).read()  # noqa: SIM115
        if re.search(pattern, content):
            return True, f"Pattern matched in {path}: {pattern!r}"
        return False, f"Pattern not found in {path}: {pattern!r}"

    return VerificationCheck(
        name=f"regex:{path}",
        check_type="deterministic",
        check_fn=_check,
        severity=severity,
    )
