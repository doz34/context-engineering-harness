"""
QW4 — MCP Trust Store (Hash Pinning)
=====================================
At boot, validate that each MCP server is in the trust store
(signed by a known publisher). Refuse unknown servers.
Closes: MCP poisoning (typosquatting, supply chain attack).
"""

import os
import json
import hashlib
import secrets
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path


# Default trust store: known publishers + their pinned hashes
# In production, this would be loaded from a signed trust list (TOFU model)
DEFAULT_TRUSTED_PUBLISHERS: Set[str] = {
    "anthropic",
    "openai",
    "google",
    "cloudflare",
    "modelcontextprotocol",
    "ce-harness-internal",
}


@dataclass
class MCPServerEntry:
    """A registered MCP server with its expected hash."""
    name: str
    publisher: str
    expected_sha256: str
    version: str
    signed_at: str  # ISO timestamp of trust signature
    signature: str  # Signature over the entry


@dataclass
class MCPBootValidation:
    """Result of MCP trust validation at boot."""
    valid: bool
    errors: List[str]
    validated_servers: List[str] = None
    rejected_servers: List[str] = None


def sha256_file(path: str) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def load_trust_store(path: str) -> Dict[str, MCPServerEntry]:
    """
    Load MCP trust store from a JSON file.
    Format: {"server_name": {name, publisher, expected_sha256, version, signed_at, signature}}
    """
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        data = json.load(f)

    store = {}
    for name, entry_data in data.items():
        store[name] = MCPServerEntry(
            name=entry_data["name"],
            publisher=entry_data["publisher"],
            expected_sha256=entry_data["expected_sha256"],
            version=entry_data["version"],
            signed_at=entry_data["signed_at"],
            signature=entry_data["signature"],
        )
    return store


def save_trust_store(path: str, store: Dict[str, MCPServerEntry]) -> None:
    """Save trust store to JSON file."""
    data = {
        name: {
            "name": entry.name,
            "publisher": entry.publisher,
            "expected_sha256": entry.expected_sha256,
            "version": entry.version,
            "signed_at": entry.signed_at,
            "signature": entry.signature,
        }
        for name, entry in store.items()
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(path, 0o600)


def sign_entry(entry: MCPServerEntry, signing_key: bytes) -> MCPServerEntry:
    """Sign a trust store entry."""
    import hmac
    content = f"{entry.name}|{entry.publisher}|{entry.expected_sha256}|{entry.version}|{entry.signed_at}".encode()
    entry.signature = hmac.new(signing_key, content, hashlib.sha256).hexdigest()
    return entry


def verify_entry_signature(entry: MCPServerEntry, signing_key: bytes) -> bool:
    """Verify HMAC signature on a trust store entry."""
    import hmac
    content = f"{entry.name}|{entry.publisher}|{entry.expected_sha256}|{entry.version}|{entry.signed_at}".encode()
    expected = hmac.new(signing_key, content, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, entry.signature)


def validate_mcp_at_boot(
    servers: Dict[str, str],  # name → file_path
    trust_store: Dict[str, MCPServerEntry],
    signing_key: Optional[bytes] = None,
    strict: bool = True,
) -> MCPBootValidation:
    """
    Validate all MCP servers at boot.
    Refuses servers not in trust store (unless strict=False for dev).
    Refuses servers whose hash doesn't match expected.
    """
    errors = []
    validated = []
    rejected = []

    for name, path in servers.items():
        if not os.path.exists(path):
            rejected.append(name)
            errors.append(f"MCP server '{name}' not found at {path}")
            continue

        actual_hash = sha256_file(path)

        if name not in trust_store:
            rejected.append(name)
            errors.append(
                f"MCP server '{name}' is NOT in trust store. "
                f"Refusing to load (typosquatting/supply chain protection)."
            )
            continue

        entry = trust_store[name]

        # Verify signature if signing_key provided
        if signing_key is not None:
            if not verify_entry_signature(entry, signing_key):
                rejected.append(name)
                errors.append(
                    f"MCP server '{name}' trust entry has INVALID signature. "
                    f"Tampering suspected."
                )
                continue

        # Verify publisher
        if entry.publisher not in DEFAULT_TRUSTED_PUBLISHERS:
            rejected.append(name)
            errors.append(
                f"MCP server '{name}' has UNTRUSTED publisher '{entry.publisher}'. "
                f"Allowed: {sorted(DEFAULT_TRUSTED_PUBLISHERS)}"
            )
            continue

        # Verify hash
        if actual_hash != entry.expected_sha256:
            rejected.append(name)
            errors.append(
                f"MCP server '{name}' hash MISMATCH. "
                f"Expected: {entry.expected_sha256[:16]}..., "
                f"Actual: {actual_hash[:16]}... "
                f"Server has been modified or is compromised."
            )
            continue

        validated.append(name)

    return MCPBootValidation(
        valid=len(rejected) == 0,
        errors=errors,
        validated_servers=validated,
        rejected_servers=rejected,
    )


# === TOFU (Trust On First Use) bootstrap helper ===

def tofu_pin(servers: Dict[str, str], publisher: str = "ce-harness-internal",
             version: str = "1.0.0") -> Dict[str, MCPServerEntry]:
    """
    Trust On First Use: pin all servers to current hashes.
    Use only when bootstrapping a new trust store from scratch.
    """
    from datetime import datetime
    store = {}
    for name, path in servers.items():
        if not os.path.exists(path):
            continue
        h = sha256_file(path)
        entry = MCPServerEntry(
            name=name, publisher=publisher,
            expected_sha256=h, version=version,
            signed_at=datetime.now().isoformat(),
            signature="",  # Will be signed externally
        )
        store[name] = entry
    return store
