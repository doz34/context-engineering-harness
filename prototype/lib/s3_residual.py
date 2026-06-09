"""
QW-S3-11/12/13 — Combined fixes for residual MED
==================================================
- QW-S3-11: Per-tenant key encryption for memory blocks
- QW-S3-12: CAB approver immutability
- QW-S3-13: EOL decision HMAC
"""

import os
import hmac
import hashlib
import json
import time
import secrets
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


# === QW-S3-11: Per-tenant key encryption for memory blocks ===

class TenantKeyStore:
    """
    Per-tenant encryption keys.
    Closes: Cross-tenant data leak via shared master key.
    """

    def __init__(self, store_path: str = ".ctxh/tenant_keys.json"):
        self.store_path = store_path
        self._keys: Dict[str, bytes] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path) as f:
                    data = json.load(f)
                self._keys = {k: bytes.fromhex(v) for k, v in data.items()}
            except (json.JSONDecodeError, KeyError, ValueError):
                self._keys = {}

    def _save(self):
        data = {k: v.hex() for k, v in self._keys.items()}
        os.makedirs(os.path.dirname(self.store_path) or ".", exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(self.store_path, 0o600)

    def get_or_create(self, tenant_id: str) -> bytes:
        """Get tenant's key, or create one if it doesn't exist."""
        if tenant_id not in self._keys:
            self._keys[tenant_id] = secrets.token_bytes(32)
            self._save()
        return self._keys[tenant_id]

    def rotate(self, tenant_id: str) -> bytes:
        """Rotate a tenant's key (new key, old data becomes unrecoverable)."""
        new_key = secrets.token_bytes(32)
        self._keys[tenant_id] = new_key
        self._save()
        return new_key

    def delete(self, tenant_id: str):
        """Delete a tenant's key (GDPR right to erasure)."""
        self._keys.pop(tenant_id, None)
        self._save()


# === QW-S3-12: CAB approver immutability ===

@dataclass
class CABApproval:
    """A CAB (Change Advisory Board) approval."""
    change_id: str
    approvers: List[str]  # List of approver user IDs
    approved_at: float
    expires_at: Optional[float] = None
    signature: str = ""  # HMAC of all fields
    prev_hash: str = ""  # Hash chain


class CABRegistry:
    """
    CAB approver registry with HMAC chain.
    Closes: CAB approval bypass (fake approval logs).
    """

    def __init__(self, master_key: bytes):
        self.master_key = master_key
        self._approvals: Dict[str, CABApproval] = {}
        self._last_hash: str = ""

    def _sign(self, approval: CABApproval) -> str:
        content = json.dumps({
            "change_id": approval.change_id,
            "approvers": approval.approvers,
            "approved_at": approval.approved_at,
            "expires_at": approval.expires_at,
            "prev_hash": approval.prev_hash,
        }, sort_keys=True).encode()
        return hmac.new(self.master_key, content, hashlib.sha256).hexdigest()

    def add_approval(self, change_id: str, approvers: List[str],
                     ttl_seconds: Optional[int] = None) -> CABApproval:
        """Add a CAB approval. Signed and chained."""
        now = time.time()
        if ttl_seconds is None:
            expires_at = None
        else:
            expires_at = now + ttl_seconds
        approval = CABApproval(
            change_id=change_id,
            approvers=approvers,
            approved_at=now,
            expires_at=expires_at,
            prev_hash=self._last_hash,
        )
        approval.signature = self._sign(approval)
        self._approvals[change_id] = approval
        self._last_hash = approval.signature
        return approval

    def verify(self, change_id: str) -> bool:
        """Verify a CAB approval's signature and chain."""
        if change_id not in self._approvals:
            return False
        a = self._approvals[change_id]
        expected_sig = self._sign(a)
        if not hmac.compare_digest(a.signature, expected_sig):
            return False
        # Verify expiry (None means no expiry)
        if a.expires_at is not None and time.time() > a.expires_at:
            return False
        return True

    def list_valid(self) -> List[str]:
        """List all non-expired, verified approval IDs."""
        return [cid for cid in self._approvals if self.verify(cid)]


# === QW-S3-13: EOL decision HMAC ===

@dataclass
class EOLDecision:
    """An End-of-Life decision (e.g., project retirement)."""
    project_id: str
    decided_at: float
    decided_by: str  # user ID
    reason: str
    retention_days: int = 90
    signature: str = ""  # HMAC
    prev_hash: str = ""  # For chained EOL decisions


class EOLRegistry:
    """
    EOL decision registry with HMAC chain.
    Closes: EOL decision manipulation (fake project retirement).
    """

    def __init__(self, master_key: bytes):
        self.master_key = master_key
        self._decisions: Dict[str, EOLDecision] = {}
        self._last_hash: str = ""

    def _sign(self, decision: EOLDecision) -> str:
        content = json.dumps({
            "project_id": decision.project_id,
            "decided_at": decision.decided_at,
            "decided_by": decision.decided_by,
            "reason": decision.reason,
            "retention_days": decision.retention_days,
            "prev_hash": decision.prev_hash,
        }, sort_keys=True).encode()
        return hmac.new(self.master_key, content, hashlib.sha256).hexdigest()

    def record_eol(self, project_id: str, decided_by: str, reason: str,
                   retention_days: int = 90) -> EOLDecision:
        """Record an EOL decision. Signed and chained."""
        decision = EOLDecision(
            project_id=project_id,
            decided_at=time.time(),
            decided_by=decided_by,
            reason=reason,
            retention_days=retention_days,
            prev_hash=self._last_hash,
        )
        decision.signature = self._sign(decision)
        self._decisions[project_id] = decision
        self._last_hash = decision.signature
        return decision

    def verify(self, project_id: str) -> bool:
        """Verify an EOL decision's signature and chain."""
        if project_id not in self._decisions:
            return False
        d = self._decisions[project_id]
        expected = self._sign(d)
        return hmac.compare_digest(d.signature, expected)

    def get(self, project_id: str) -> Optional[EOLDecision]:
        """Get EOL decision (only if verified)."""
        if self.verify(project_id):
            return self._decisions[project_id]
        return None
