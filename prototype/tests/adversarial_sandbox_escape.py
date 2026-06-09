"""
Adversarial test: Sandbox Escape Attempts
==========================================
Tests that the AST-based sandbox rejects known escape patterns.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.code_api import CodeAPISandbox, SandboxVerdict, agent_can_use


# === ATTACK 1: Standard os.system escape ===
def test_sandbox_blocks_os_system():
    code = "import os\nos.system('cat /etc/passwd')"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 2: subprocess escape ===
def test_sandbox_blocks_subprocess():
    code = "import subprocess\nsubprocess.run(['cat', '/etc/passwd'])"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 3: Dunder attribute traversal ===
def test_sandbox_blocks_dunder_subclasses():
    code = """
classes = ().__class__.__subclasses__()
for c in classes:
    if 'Popen' in c.__name__:
        c(['cat', '/etc/passwd'])
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 4: Builtin __import__ via getattr ===
def test_sandbox_blocks_getattr_chain():
    code = """
import builtins
getattr(builtins, '__import__')('os').system('rm -rf /')
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 5: exec with encoded string ===
def test_sandbox_blocks_exec_with_string():
    code = "exec('import os; os.system(\"id\")')"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 6: Network request ===
def test_sandbox_blocks_network_request():
    code = "import urllib.request; urllib.request.urlopen('http://attacker.com')"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 7: File write (might be legitimate but dangerous) ===
def test_sandbox_blocks_open_write():
    code = "open('/etc/passwd', 'w').write('pwned')"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 8: Pickle deserialization ===
def test_sandbox_blocks_pickle():
    code = "import pickle; pickle.loads(b'cos\\nsystem\\n(S\"id\"\\ntR.')"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 9: Safe arithmetic still works ===
def test_sandbox_allows_safe_arithmetic():
    code = """
result = 0
for i in range(10):
    result += i * 2
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.ALLOW


# === ATTACK 10: Read-only file (might be safe but still blocked) ===
def test_sandbox_blocks_file_read():
    """Even file reads are blocked (defense in depth)."""
    code = "data = open('/etc/passwd', 'r').read()"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 11: String-based exec via compile ===
def test_sandbox_blocks_compile_exec():
    code = """
src = '__import__("os").system("id")'
compile(src, '<string>', 'exec')
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 12: Class hierarchy walk ===
def test_sandbox_blocks_mro_walk():
    code = """
for klass in ().__class__.__mro__:
    print(klass.__subclasses__())
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 13: agent_can_use helper ===
def test_agent_can_use_helper():
    code = "import os"
    s = CodeAPISandbox()
    r = agent_can_use(s, code)
    assert r.verdict == SandboxVerdict.DENY


# === ATTACK 14: Safe code passes ===
def test_sandbox_allows_string_manipulation():
    code = """
text = "hello world"
parts = text.split(" ")
result = " ".join(reversed(parts))
print(result)
"""
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.ALLOW
    assert "world hello" in r.stdout


# === ATTACK 15: SyntaxError is denied, not crashed ===
def test_sandbox_handles_syntax_error():
    code = "def invalid(:\n  pass"
    s = CodeAPISandbox()
    r = s.run(code)
    assert r.verdict == SandboxVerdict.DENY
    assert "SyntaxError" in r.denied_reasons[0]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
