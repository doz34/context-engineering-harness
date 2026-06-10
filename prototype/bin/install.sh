#!/usr/bin/env bash
# CE-Harness POV minimal installer
# No external dependencies — pure Python stdlib.

set -e

cd "$(dirname "$0")/.."

echo "═══════════════════════════════════════════════════════════════"
echo "  CE-Harness POV — Installation"
echo "═══════════════════════════════════════════════════════════════"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 not found. Install Python 3.10+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PY_VERSION found"

# Check stdlib modules we need
for mod in sqlite3 hashlib hmac json; do
    if ! python3 -c "import $mod" 2>/dev/null; then
        echo "❌ Module $mod not available (should be stdlib)"
        exit 1
    fi
done
echo "✓ All stdlib modules available"

# Make bin/ executable
chmod +x bin/ctxh bin/ctxh-demo 2>/dev/null || true
echo "✓ Binaries made executable"

# Test
echo ""
echo "▶ Testing POV..."
./bin/ctxh --help

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Installation complete"
echo "  Next: ./bin/ctxh-demo"
echo "═══════════════════════════════════════════════════════════════"
