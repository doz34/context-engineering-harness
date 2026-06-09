"""
QW-S3-2 — Container Image SHA-256 Pinning
============================================
Helper module for converting mutable Docker image tags to
immutable SHA-256 digests. Closes: Image tag hijacking.
"""

import re
import os
import json
import hashlib
import subprocess
from typing import Optional, Dict, List
from dataclasses import dataclass


SHA256_PATTERN = re.compile(r'^sha256:[a-f0-9]{64}$')
SHA256_RAW_PATTERN = re.compile(r'^[a-f0-9]{64}$')
# Mutable tags that should be refused
MUTABLE_TAGS = {
    "latest", "main", "master", "develop", "dev", "staging", "prod",
    "production", "edge", "stable", "next", "current", "head",
    "trunk", "default", "tip", "release",
}


@dataclass
class ImageRef:
    """Parsed Docker image reference."""
    registry: str
    repo: str
    tag: Optional[str]
    digest: Optional[str]  # sha256:...

    def is_pinned(self) -> bool:
        return self.digest is not None

    def is_mutable(self) -> bool:
        """A reference is mutable if it has a tag but no digest."""
        return self.tag is not None and self.digest is None

    def to_immutable(self) -> str:
        """Return immutable form (digest if pinned, else original)."""
        if self.digest:
            return f"{self.registry}/{self.repo}@{self.digest}"
        return f"{self.registry}/{self.repo}:{self.tag}" if self.tag else f"{self.registry}/{self.repo}"


def parse_image_ref(ref: str) -> ImageRef:
    """
    Parse a Docker image reference like:
      - python:3.12
      - python:3.12@sha256:abc...
      - gcr.io/proj/image:v1@sha256:abc...
      - ghcr.io/org/img:tag
    """
    ref = ref.strip()
    if not ref:
        return ImageRef(registry="", repo="", tag=None, digest=None)

    # Split off digest if present
    digest = None
    if "@" in ref:
        ref, digest_full = ref.rsplit("@", 1)
        if SHA256_PATTERN.match(digest_full):
            digest = digest_full
        elif SHA256_RAW_PATTERN.match(digest_full):
            digest = f"sha256:{digest_full}"

    # Split off tag
    tag = None
    if ":" in ref.split("/")[-1]:
        # Tag is after the last colon in the last segment
        parts = ref.rsplit(":", 1)
        ref_no_tag = parts[0]
        tag = parts[1]
    else:
        ref_no_tag = ref

    # Split registry from repo
    # Default registry is docker.io (Docker Hub)
    # Heuristic: if the first segment contains a '.' or ':' or is 'localhost', it's a registry
    parts = ref_no_tag.split("/")
    first_is_registry = (
        len(parts) > 1
        and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost")
    )
    if first_is_registry:
        registry = parts[0]
        repo = "/".join(parts[1:])
    else:
        # docker.io is implicit
        registry = "docker.io"
        repo = "/".join(parts)

    return ImageRef(registry=registry, repo=repo, tag=tag, digest=digest)


def is_mutable_tag(tag: str) -> bool:
    return tag.lower() in MUTABLE_TAGS


def validate_image_ref(ref: str) -> tuple[bool, list[str]]:
    """
    Validate a Docker image reference for production use.
    Returns (is_valid, issues).
    """
    issues = []
    parsed = parse_image_ref(ref)

    if not parsed.repo:
        issues.append("Empty image reference")
        return (False, issues)

    if parsed.is_mutable():
        issues.append(
            f"Image '{ref}' is mutable (tag '{parsed.tag}' without digest). "
            f"Pin to @sha256:... for immutable deployment."
        )

    if parsed.tag and is_mutable_tag(parsed.tag):
        issues.append(
            f"Image '{ref}' uses mutable tag '{parsed.tag}'. "
            f"Refuse :latest, :main, etc. Pin to specific version + digest."
        )

    return (len(issues) == 0, issues)


# === TOFU (Trust On First Use) for known registries ===

def resolve_digest_via_registry(image_ref: str) -> Optional[str]:
    """
    Resolve the SHA-256 digest of an image via the registry API.
    Requires `skopeo` or `docker` CLI to be available.

    Returns the digest as 'sha256:...' or None if unable to resolve.
    """
    # First, check if the image is already pinned
    parsed = parse_image_ref(image_ref)
    if parsed.digest:
        return parsed.digest

    # Try skopeo (preferred for read-only, no daemon)
    try:
        result = subprocess.run(
            ["skopeo", "inspect", f"docker://{image_ref}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            digest = info.get("Digest")
            if digest:
                return digest
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    # Try docker (requires daemon)
    try:
        result = subprocess.run(
            ["docker", "inspect", image_ref, "--format", "{{.Id}}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            digest_id = result.stdout.strip()
            if digest_id.startswith("sha256:"):
                return digest_id
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def pin_to_digest(image_ref: str) -> Optional[str]:
    """
    Convert a mutable image reference to an immutable digest.
    Returns the pinned reference or None if unable to resolve.
    """
    digest = resolve_digest_via_registry(image_ref)
    if not digest:
        return None
    parsed = parse_image_ref(image_ref)
    return f"{parsed.registry}/{parsed.repo}@{digest}"


# === Image policy enforcement ===

class ImagePolicy:
    """
    Policy for image references in a project.
    Refuses mutable tags in production contexts.
    """

    def __init__(self, allowed_tags: Optional[set] = None, deny_latest: bool = True):
        self.allowed_tags = allowed_tags or set()
        self.deny_latest = deny_latest

    def check(self, image_ref: str) -> tuple[bool, list[str]]:
        """Check if image_ref complies with policy."""
        issues = []
        parsed = parse_image_ref(image_ref)

        if not parsed.is_pinned():
            issues.append(
                f"Image '{image_ref}' is not pinned. "
                f"Production policy requires @sha256:... digest."
            )

        if parsed.tag and self.deny_latest and is_mutable_tag(parsed.tag):
            issues.append(
                f"Image '{image_ref}' uses mutable tag '{parsed.tag}'. "
                f"Refused by policy."
            )

        if parsed.tag and self.allowed_tags and parsed.tag not in self.allowed_tags:
            issues.append(
                f"Image tag '{parsed.tag}' not in allowed list: {sorted(self.allowed_tags)}"
            )

        return (len(issues) == 0, issues)
