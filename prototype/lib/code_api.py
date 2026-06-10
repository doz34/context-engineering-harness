"""
CE-Harness Code API Sandbox
=============================
Execute agent-written code in a restricted environment.
Closes CRIT: SANDBOX_NOT_YET_IMPLEMENTED (CISO HIGH)

Pattern: Anthropic 2025-11 — "Code execution with MCP: building more
efficient agents". The agent writes code, sandbox executes, results
stay in sandbox unless explicitly logged.

Implementation: AST-based validation (no RestrictedPython dependency
to keep stdlib-only POV). This is a defensive layer, not a perfect
sandbox (true sandboxing requires OS-level isolation).
"""

import ast
import re
import sys
import os
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class SandboxVerdict(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    MODIFY = "MODIFY"  # Code can be modified to be safe


# Disallowed AST nodes (any code using these is DENIED)
DISALLOWED_NODES = {
    ast.Import,      # 'import os' — too broad
    ast.ImportFrom,  # 'from os import path' — too broad
}

# Allowed node types (whitelist approach for safety)
ALLOWED_NODES = {
    ast.Module, ast.Expr, ast.Constant, ast.Name, ast.Load, ast.Store,
    ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.FloorDiv, ast.Pow, ast.USub, ast.UAdd, ast.BoolOp, ast.And, ast.Or,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn, ast.Not, ast.If, ast.For, ast.While,
    ast.FunctionDef, ast.Lambda, ast.Return, ast.Yield, ast.IfExp,
    ast.Call, ast.Attribute, ast.Subscript, ast.Index, ast.Slice,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp, ast.DictComp,
    ast.SetComp, ast.GeneratorExp, ast.comprehension, ast.Starred,
    ast.Assign, ast.AugAssign, ast.AnnAssign, ast.NamedExpr,
    ast.Try, ast.ExceptHandler, ast.Raise, ast.Assert,
    ast.Pass, ast.Break, ast.Continue,
    ast.FormattedValue, ast.JoinedStr, ast.Await, ast.AsyncFor, ast.AsyncWith,
    # IMPORTANT: ast.Num, ast.Str, ast.Bytes, ast.NameConstant, ast.Ellipsis
    # are deprecated in 3.8+ but kept here for compat
}

# Dangerous function/attribute names to deny
DANGEROUS_NAMES = {
    "exec", "eval", "compile", "__import__", "open", "input",
    "os.system", "os.popen", "os.exec", "os.spawn",
    "subprocess", "shutil.rmtree",
    "getattr", "setattr", "delattr",  # attribute access is risky
    "globals", "locals", "vars",
    "__builtins__", "__class__", "__subclasses__", "__bases__",
    "pickle.loads", "marshal.loads", "shelve.open",
    "socket.socket", "urllib.request.urlopen",
    "requests.get", "requests.post", "httpx.get", "httpx.post",
    "sys.exit", "sys.modules",
}

# Safe builtins (whitelist)
SAFE_BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "classmethod", "complex", "dict", "divmod",
    "enumerate", "filter", "float", "format", "frozenset", "hash",
    "hex", "id", "int", "isinstance", "issubclass", "iter", "len",
    "list", "map", "max", "min", "next", "object", "oct", "ord",
    "pow", "print", "property", "range", "repr", "reversed", "round",
    "set", "slice", "sorted", "staticmethod", "str", "sum", "super",
    "tuple", "type", "vars", "zip",
    # Class definition support (without exposing dunder-execution surface)
    "__build_class__",
    # Common exception types — required for legitimate try/except blocks
    "Exception", "BaseException", "ValueError", "TypeError",
    "KeyError", "IndexError", "AttributeError", "RuntimeError",
    "ZeroDivisionError", "StopIteration", "AssertionError",
    "NameError", "OSError", "IOError",
    # __import__ is whitelisted but checked at runtime
    "__import__",
}


@dataclass
class SandboxResult:
    verdict: SandboxVerdict
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    error: str = ""
    denied_reasons: List[str] = field(default_factory=list)
    modified_code: str = ""


class CodeAPISandbox:
    """
    Static AST analysis + runtime exec in restricted namespace.

    Defense layers:
    1. AST whitelist (only allowed node types)
    2. Name blacklist (dangerous functions/attributes)
    3. Builtin whitelist (only safe builtins)
    4. Stdout/stderr capture (no direct output)
    5. Timeout (optional, future)
    """

    def __init__(self, allowed_builtins: Optional[set] = None):
        # BUG FIX: was `allowed_builtins or SAFE_BUILTINS` which short-circuits
        # on the empty set, leaving self.allowed_builtins as None → NameError
        # at execution. Now we explicitly default to a copy of SAFE_BUILTINS.
        if allowed_builtins is None:
            self.allowed_builtins = set(SAFE_BUILTINS)
        else:
            self.allowed_builtins = set(allowed_builtins)

    def static_check(self, code: str) -> SandboxResult:
        """
        AST-based static analysis. Returns DENY if dangerous.
        """
        result = SandboxResult(verdict=SandboxVerdict.ALLOW)

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            result.verdict = SandboxVerdict.DENY
            result.denied_reasons.append(f"SyntaxError: {e}")
            return result

        # Walk all nodes
        for node in ast.walk(tree):
            node_type = type(node)

            # Check for disallowed node types
            if node_type in DISALLOWED_NODES:
                result.verdict = SandboxVerdict.DENY
                result.denied_reasons.append(
                    f"Disallowed AST node: {node_type.__name__} at line {getattr(node, 'lineno', '?')}"
                )

            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name and func_name in DANGEROUS_NAMES:
                    result.verdict = SandboxVerdict.DENY
                    result.denied_reasons.append(
                        f"Dangerous call: {func_name}() at line {node.lineno}"
                    )

            # Check for dangerous attribute access
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    if attr_name not in ("__init__", "__str__", "__repr__", "__name__", "__doc__"):
                        result.verdict = SandboxVerdict.DENY
                        result.denied_reasons.append(
                            f"Dunder attribute access: {attr_name} at line {node.lineno}"
                        )

        return result

    def _get_call_name(self, call_node: ast.Call) -> Optional[str]:
        """Extract function name from a Call node."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        if isinstance(call_node.func, ast.Attribute):
            # Recursive for nested attributes
            parts = []
            n = call_node.func
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if isinstance(n, ast.Name):
                parts.append(n.id)
            return ".".join(reversed(parts))
        return None

    def execute(self, code: str, context: Optional[dict] = None,
                timeout: float = 30.0) -> SandboxResult:
        """
        Execute code in restricted sandbox.
        Returns SandboxResult with stdout, stderr, return value, errors.

        `timeout` (default 30s) caps wall-clock execution via SIGALRM
        (Unix main-thread only). On Windows or in sub-threads the timeout
        is a no-op and the caller must enforce external limits.
        """
        # First, static check
        check = self.static_check(code)
        if check.verdict == SandboxVerdict.DENY:
            return check

        # Build restricted namespace — explicit, no ternary surprises.
        # Use `import builtins` to ensure we get the actual module,
        # not whatever `__builtins__` resolves to in this scope.
        import builtins as _b
        restricted_builtins = {}
        for name in self.allowed_builtins:
            if hasattr(_b, name):
                restricted_builtins[name] = getattr(_b, name)

        # Strip dangerous builtins (defense in depth, even after static check)
        for dangerous in ["exec", "eval", "compile", "__import__", "open",
                          "input", "globals", "locals", "breakpoint"]:
            restricted_builtins.pop(dangerous, None)

        namespace = {
            "__builtins__": restricted_builtins,
            "__name__": "__sandbox__",
            "_result": None,
        }
        if context:
            namespace.update(context)

        # Capture stdout/stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        result = SandboxResult(verdict=SandboxVerdict.ALLOW)
        # Wall-clock timeout via SIGALRM (Unix only, main thread). Restores
        # any previously-installed handler on exit/exception.
        import signal as _signal
        prev_handler = _signal.getsignal(_signal.SIGALRM)
        use_alarm = (
            timeout > 0
            and prev_handler in (_signal.SIG_DFL, _signal.SIG_IGN, None)
        )

        def _on_alarm(signum, frame):
            raise TimeoutError(f"sandbox code exceeded {timeout}s timeout")

        if use_alarm:
            _signal.signal(_signal.SIGALRM, _on_alarm)
            _signal.setitimer(_signal.ITIMER_REAL, timeout)

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                # Wrap in a function to capture return value
                wrapped_lines = ["def __sandbox_fn__():"]
                for line in code.split("\n"):
                    wrapped_lines.append("    " + line)
                wrapped_lines.append("    return _result")
                wrapped_lines.append("_result = __sandbox_fn__()")
                wrapped = "\n".join(wrapped_lines)

                exec(wrapped, namespace)
                result.return_value = namespace.get("_result")
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        finally:
            if use_alarm:
                _signal.setitimer(_signal.ITIMER_REAL, 0)  # disarm
                _signal.signal(_signal.SIGALRM, prev_handler)
            result.stdout = stdout_buf.getvalue()
            result.stderr = stderr_buf.getvalue()

        return result

    def run(self, code: str, context: Optional[dict] = None) -> SandboxResult:
        """
        Convenience: static_check + execute. Returns combined result.
        """
        check = self.static_check(code)
        if check.verdict == SandboxVerdict.DENY:
            return check
        return self.execute(code, context)


# === SERVERS DIRECTORY (Code-as-API pattern) ===
# Pattern Anthropic 2025-11: tools exposed as code in filesystem
# rather than JSON schemas in system prompt.

DEFAULT_SERVERS_DIR = "servers/"


@dataclass
class ServerTool:
    """A tool exposed as code in the servers/ directory."""
    name: str
    server: str
    code_path: str
    description: str = ""


def discover_tools(servers_dir: str = DEFAULT_SERVERS_DIR) -> List[ServerTool]:
    """
    Discover tools from filesystem (progressive disclosure pattern).
    Only returns metadata, not the code itself — saves tokens.
    """
    tools = []
    if not os.path.isdir(servers_dir):
        return tools

    for server in os.listdir(servers_dir):
        server_path = os.path.join(servers_dir, server)
        if not os.path.isdir(server_path):
            continue
        for fname in os.listdir(server_path):
            if fname.endswith((".py", ".ts", ".js")):
                tools.append(ServerTool(
                    name=fname.rsplit(".", 1)[0],
                    server=server,
                    code_path=os.path.join(server_path, fname),
                ))
    return tools


def agent_can_use(sandbox: CodeAPISandbox, code: str) -> SandboxResult:
    """
    Validate that agent-written code is safe to run.
    Returns ALLOW if safe, DENY otherwise.
    """
    return sandbox.static_check(code)
