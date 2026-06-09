"""Test Code API Sandbox (Fix 3)."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.code_api import CodeAPISandbox, SandboxVerdict, discover_tools


def test_sandbox_imports():
    s = CodeAPISandbox()
    assert s is not None


def test_allow_simple_code():
    s = CodeAPISandbox()
    r = s.static_check("x = 1 + 2\nprint(x)")
    assert r.verdict == SandboxVerdict.ALLOW


def test_allow_arithmetic():
    s = CodeAPISandbox()
    r = s.static_check("result = 10 * 5 + 3")
    assert r.verdict == SandboxVerdict.ALLOW


def test_allow_function_def():
    s = CodeAPISandbox()
    r = s.static_check("""
def add(a, b):
    return a + b
result = add(1, 2)
""")
    assert r.verdict == SandboxVerdict.ALLOW


def test_deny_import():
    s = CodeAPISandbox()
    r = s.static_check("import os\nos.system('rm -rf /')")
    assert r.verdict == SandboxVerdict.DENY
    assert any("import" in reason.lower() for reason in r.denied_reasons)


def test_deny_from_import():
    s = CodeAPISandbox()
    r = s.static_check("from os import system\nsystem('ls')")
    assert r.verdict == SandboxVerdict.DENY


def test_deny_exec_call():
    s = CodeAPISandbox()
    r = s.static_check("exec('print(1)')")
    assert r.verdict == SandboxVerdict.DENY
    assert any("exec" in reason.lower() for reason in r.denied_reasons)


def test_deny_eval_call():
    s = CodeAPISandbox()
    r = s.static_check("eval('1+1')")
    assert r.verdict == SandboxVerdict.DENY


def test_deny_open_call():
    s = CodeAPISandbox()
    r = s.static_check("f = open('/etc/passwd', 'r')")
    assert r.verdict == SandboxVerdict.DENY


def test_deny_dunder_attribute():
    """__subclasses__ etc. blocked."""
    s = CodeAPISandbox()
    r = s.static_check("x = ().__class__.__subclasses__()")
    assert r.verdict == SandboxVerdict.DENY


def test_allow_safe_builtins():
    """Safe builtins (print, len, range) allowed."""
    s = CodeAPISandbox()
    r = s.static_check("""
for i in range(10):
    print(i)
""")
    assert r.verdict == SandboxVerdict.ALLOW


def test_execute_simple_code():
    s = CodeAPISandbox()
    r = s.execute("x = 1 + 2\nprint(x)")
    assert r.verdict == SandboxVerdict.ALLOW
    assert "3" in r.stdout


def test_execute_captures_stdout():
    s = CodeAPISandbox()
    r = s.execute("print('hello')\nprint('world')")
    assert "hello" in r.stdout
    assert "world" in r.stdout


def test_execute_dangerous_code_blocked():
    s = CodeAPISandbox()
    r = s.execute("import os")
    assert r.verdict == SandboxVerdict.DENY
    assert "Import" in r.denied_reasons[0] or "import" in r.denied_reasons[0]


def test_execute_syntax_error():
    s = CodeAPISandbox()
    r = s.execute("def foo(:\n    pass")
    assert r.verdict == SandboxVerdict.DENY
    assert "SyntaxError" in r.denied_reasons[0]


def test_execute_runtime_error_captured():
    s = CodeAPISandbox()
    r = s.execute("1 / 0")
    # Static check passes, but execution fails
    assert r.verdict == SandboxVerdict.ALLOW  # static check is ALLOW
    assert "ZeroDivisionError" in r.error


def test_run_combines_check_and_execute():
    s = CodeAPISandbox()
    r = s.run("print('test')")
    assert r.verdict == SandboxVerdict.ALLOW
    assert "test" in r.stdout


def test_run_dangerous_short_circuits():
    s = CodeAPISandbox()
    r = s.run("import os")
    assert r.verdict == SandboxVerdict.DENY
    # No execution attempted
    assert r.stdout == ""


def test_discover_tools_empty():
    with tempfile.TemporaryDirectory() as d:
        tools = discover_tools(servers_dir=os.path.join(d, "servers"))
        assert tools == []


def test_discover_tools_finds_python_files():
    with tempfile.TemporaryDirectory() as d:
        servers = os.path.join(d, "servers")
        os.makedirs(os.path.join(servers, "google-drive"))
        with open(os.path.join(servers, "google-drive", "getDocument.py"), "w") as f:
            f.write("# tool")
        with open(os.path.join(servers, "google-drive", "listFiles.py"), "w") as f:
            f.write("# tool")
        tools = discover_tools(servers_dir=servers)
        names = [t.name for t in tools]
        assert "getDocument" in names
        assert "listFiles" in names
        assert all(t.server == "google-drive" for t in tools)


def test_progressive_disclosure_only_metadata():
    """discover_tools returns metadata only, not code content."""
    with tempfile.TemporaryDirectory() as d:
        servers = os.path.join(d, "servers")
        os.makedirs(os.path.join(servers, "test"))
        with open(os.path.join(servers, "test", "secret_tool.py"), "w") as f:
            f.write("SECRET_API_KEY = 'real_secret_xyz'")
        tools = discover_tools(servers_dir=servers)
        # No tool description contains the secret
        for t in tools:
            assert "real_secret_xyz" not in t.code_path
            assert "real_secret_xyz" not in t.description
        # Code is NOT loaded into memory
        assert all("SECRET_API_KEY" not in str(t.__dict__) for t in tools)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
