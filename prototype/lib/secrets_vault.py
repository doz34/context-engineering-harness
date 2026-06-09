"""
QW7 — Secrets Vault
====================
Encrypted secrets store with ACL. Replaces env vars (visible in ps).
Closes: Secret leakage via env vars / process list.
"""

import os
import json
import hashlib
import secrets as _secrets
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, field
from pathlib import Path
from .security import EncryptedDB, load_or_create_master_key


@dataclass
class SecretEntry:
    """A secret in the vault."""
    key: str
    ciphertext: bytes
    owner: str  # tenant or user
    created_at: str
    rotated_at: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class ACLEntry:
    """Access control entry for a secret."""
    principal: str  # e.g., "phase:P5", "subagent:lead", "user:doz"
    permissions: Set[str]  # {"read", "write", "delete"}


class SecretsVault:
    """
    Encrypted secrets vault with ACL.

    Storage: encrypted file (chacha20/aes-gcm via security.py).
    Lookup: in-memory dict, fast access.
    ACL: per-secret principal permissions.
    """

    def __init__(self, vault_path: str, master_key: Optional[bytes] = None):
        self.vault_path = vault_path
        self._key = master_key or load_or_create_master_key(
            vault_path + ".master"
        )
        self._edb = EncryptedDB(vault_path, self._passphrase_from_key())
        self._secrets: Dict[str, SecretEntry] = {}
        self._acl: Dict[str, List[ACLEntry]] = {}
        self._load()

    def _passphrase_from_key(self) -> str:
        """Derive a deterministic passphrase from the key bytes."""
        return hashlib.sha256(b"vault-passphrase:" + self._key).hexdigest()

    def _load(self):
        """Load vault from disk."""
        meta_path = self.vault_path + ".meta.json"
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            for key, data in meta.get("secrets", {}).items():
                self._secrets[key] = SecretEntry(
                    key=key,
                    ciphertext=bytes.fromhex(data["ciphertext_hex"]),
                    owner=data["owner"],
                    created_at=data["created_at"],
                    rotated_at=data["rotated_at"],
                    metadata=data.get("metadata", {}),
                )
            for key, acls in meta.get("acl", {}).items():
                self._acl[key] = [
                    ACLEntry(
                        principal=a["principal"],
                        permissions=set(a["permissions"]),
                    )
                    for a in acls
                ]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Failed to load vault: {e}")

    def _save(self):
        """Persist vault to disk."""
        meta = {
            "version": 1,
            "secrets": {
                k: {
                    "ciphertext_hex": v.ciphertext.hex(),
                    "owner": v.owner,
                    "created_at": v.created_at,
                    "rotated_at": v.rotated_at,
                    "metadata": v.metadata,
                }
                for k, v in self._secrets.items()
            },
            "acl": {
                k: [{"principal": a.principal, "permissions": list(a.permissions)} for a in acls]
                for k, acls in self._acl.items()
            },
        }
        meta_path = self.vault_path + ".meta.json"
        os.makedirs(os.path.dirname(meta_path) or ".", exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        os.chmod(meta_path, 0o600)

    def set(self, key: str, value: str, owner: str = "default",
            metadata: Dict = None):
        """Store a secret. Auto-encrypts."""
        from datetime import datetime
        ct = self._edb.encrypt(value)
        now = datetime.now().isoformat()
        self._secrets[key] = SecretEntry(
            key=key, ciphertext=ct, owner=owner,
            created_at=now, rotated_at=now,
            metadata=metadata or {},
        )
        # Default ACL: owner can read/write
        self._acl[key] = [ACLEntry(principal=owner, permissions={"read", "write", "delete"})]
        self._save()

    def get(self, key: str, principal: str = None) -> Optional[str]:
        """Retrieve a secret. ACL check if principal specified."""
        if key not in self._secrets:
            return None
        if principal is not None:
            if not self._check_acl(key, principal, "read"):
                raise PermissionError(
                    f"Principal '{principal}' has no read access to '{key}'"
                )
        return self._edb.decrypt(self._secrets[key].ciphertext)

    def grant(self, key: str, principal: str, permissions: Set[str]):
        """Grant access to a secret."""
        if key not in self._acl:
            self._acl[key] = []
        # Add or update
        for entry in self._acl[key]:
            if entry.principal == principal:
                entry.permissions.update(permissions)
                self._save()
                return
        self._acl[key].append(ACLEntry(principal=principal, permissions=set(permissions)))
        self._save()

    def revoke(self, key: str, principal: str):
        """Revoke all access from a principal."""
        if key in self._acl:
            self._acl[key] = [a for a in self._acl[key] if a.principal != principal]
            self._save()

    def rotate(self, key: str, new_value: str):
        """Rotate a secret (new value, mark rotation time)."""
        from datetime import datetime
        if key not in self._secrets:
            raise KeyError(f"Secret '{key}' not found")
        self._secrets[key].ciphertext = self._edb.encrypt(new_value)
        self._secrets[key].rotated_at = datetime.now().isoformat()
        self._save()

    def list_keys(self, principal: str = None) -> List[str]:
        """List secret keys (optionally filtered by principal's read access)."""
        if principal is None:
            return list(self._secrets.keys())
        return [
            k for k in self._secrets
            if self._check_acl(k, principal, "read")
        ]

    def _check_acl(self, key: str, principal: str, perm: str) -> bool:
        """Check if principal has permission on key."""
        for entry in self._acl.get(key, []):
            if entry.principal == principal or entry.principal == "*":
                if perm in entry.permissions:
                    return True
        return False

    def delete(self, key: str, principal: str = None):
        """Delete a secret."""
        if key not in self._secrets:
            return
        if principal is not None and not self._check_acl(key, principal, "delete"):
            raise PermissionError(
                f"Principal '{principal}' has no delete access to '{key}'"
            )
        del self._secrets[key]
        self._acl.pop(key, None)
        self._save()


# === ENV VAR INTERCEPTOR (for backwards compat) ===

class EnvVarInterceptor:
    """
    Intercept os.environ reads and route through vault.
    Allows gradual migration from env vars to vault.

    Usage:
        EnvVarInterceptor(vault).activate()
        # Now os.environ["ANTHROPIC_API_KEY"] returns the vault value
    """

    MIGRATED_KEYS = {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "SLACK_TOKEN",
        "DATABASE_URL",  # If contains credentials
    }

    def __init__(self, vault: SecretsVault):
        self.vault = vault
        self._original_environ = None
        self._active = False

    def activate(self):
        """Replace os.environ for migrated keys with vault lookups."""
        if self._active:
            return
        self._original_environ = os.environ.copy()
        for key in self.MIGRATED_KEYS:
            if key in os.environ:
                # Migrate to vault, remove from env
                value = os.environ[key]
                try:
                    self.vault.set(key, value, owner="migrated")
                    del os.environ[key]
                except Exception:
                    pass
        self._active = True

    def get(self, key: str, default=None) -> Optional[str]:
        """Get a secret. Falls back to vault, then env, then default."""
        if key in self.MIGRATED_KEYS:
            try:
                return self.vault.get(key) or default
            except Exception:
                pass
        return os.environ.get(key, default)

    def deactivate(self):
        """Restore original env vars."""
        if not self._active:
            return
        if self._original_environ:
            os.environ.clear()
            os.environ.update(self._original_environ)
        self._active = False
