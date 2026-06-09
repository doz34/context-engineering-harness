"""
QW-S3-1 — CI/CD Pipeline Pinning
====================================
Validate that CI/CD configs (GitHub Actions, GitLab CI) use
immutable SHA-256 references instead of mutable tags (:latest, :main).
Closes: CI/CD poisoning via tag hijacking.
"""

import re
import hashlib
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# === Mutable tag patterns (refused) ===
MUTABLE_TAGS = {
    "latest", "main", "master", "develop", "dev", "staging", "prod",
    "production", "edge", "stable", "next", "current", "head",
    "trunk", "default", "tip",
}

# SHA-256 digest pattern (Docker)
SHA256_PATTERN = re.compile(r'^sha256:[a-f0-9]{64}$')
# SHA-1 pattern (GitHub Actions commit SHAs are 40 hex chars)
SHA1_PATTERN = re.compile(r'^[a-f0-9]{40}$')

# Image reference: registry/repo:tag or registry/repo@digest
IMAGE_REF_PATTERN = re.compile(
    r'^([a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?/)?'  # registry (optional)
    r'([a-z0-9]+(?:[._/-][a-z0-9]+)*?)'                 # repo
    r'(?:[:@](.+))?$'                                     # tag or digest
)


@dataclass
class PinningIssue:
    severity: str  # "ERROR" | "WARN"
    location: str
    message: str


@dataclass
class PinningResult:
    is_valid: bool
    issues: List[PinningIssue]
    pinned_count: int = 0
    mutable_count: int = 0


def is_mutable_tag(tag: str) -> bool:
    """Returns True if the tag is mutable (can be re-pointed)."""
    if not tag:
        return True
    tag_lower = tag.lower()
    if tag_lower in MUTABLE_TAGS:
        return True
    # Date-based tags like "20240101" are technically mutable
    if re.match(r'^\d{8}$', tag) or re.match(r'^v?\d+\.\d+\.\d+$', tag):
        # Date or semver tags — mutable but acceptable practice
        # We don't block them, just warn
        return False
    return False


def is_pinned_digest(ref: str) -> bool:
    """Returns True if the reference is an immutable SHA digest (1 or 256)."""
    if "@" not in ref:
        return False
    digest = ref.split("@")[-1]
    # SHA-256 with explicit prefix
    if SHA256_PATTERN.match(digest):
        return True
    # SHA-1 (40 hex chars, no prefix) — used by GitHub Actions
    if SHA1_PATTERN.match(digest):
        return True
    return False


def validate_github_action(uses_line: str) -> List[PinningIssue]:
    """
    Validate a GitHub Actions `uses:` line.
    Examples:
      - uses: actions/checkout@v4        ❌ (mutable tag)
      - uses: actions/checkout@b4ffde4...  ✅ (SHA pinned)
      - uses: ./my-action               ✅ (local, no SHA needed)
    """
    issues = []
    match = re.search(r'uses:\s*([^\s]+)', uses_line)
    if not match:
        return issues
    ref = match.group(1).strip()
    if not ref:
        issues.append(PinningIssue("ERROR", uses_line, "Empty `uses:` reference"))
        return issues

    # Local actions (./foo or ../foo) don't need SHA
    if ref.startswith("./") or ref.startswith("../") or ref.startswith("/"):
        return issues

    if is_pinned_digest(ref):
        return issues  # OK
    if "@" in ref:
        # Has @ but not pinned format
        # Check if the part after @ is a mutable tag (like v4)
        tag_part = ref.split("@")[-1]
        if is_mutable_tag(tag_part):
            issues.append(PinningIssue(
                "ERROR", uses_line,
                f"GitHub Action '{ref}' uses mutable tag '{tag_part}'. "
                f"Pin to full 40-char commit SHA.",
            ))
        else:
            issues.append(PinningIssue(
                "ERROR", uses_line,
                f"GitHub Action '{ref}' is not SHA pinned. Use full 40-char commit SHA.",
            ))
        return issues
    # No @, just tag/branch
    if "/" in ref:
        # ref is like "actions/checkout@v4" or "actions/checkout"
        parts = ref.split("/")
        if len(parts) >= 2 and "@" not in parts[-1]:
            # Mutable
            issues.append(PinningIssue(
                "ERROR", uses_line,
                f"GitHub Action '{ref}' uses mutable tag/branch. "
                f"Pin to full 40-char commit SHA (e.g., @b4ffde...)."
            ))
    return issues


def validate_docker_image(image_ref: str) -> List[PinningIssue]:
    """
    Validate a Docker image reference.
    Examples:
      - image: python:3.12        ❌ (mutable tag, not digest)
      - image: python:3.12-slim  ❌ (mutable tag, not digest)
      - image: python@sha256:abc...  ✅
      - image: gcr.io/proj/img@sha256:abc...  ✅
    """
    issues = []
    if not image_ref or not image_ref.strip():
        issues.append(PinningIssue("ERROR", image_ref, "Empty image reference"))
        return issues

    ref = image_ref.strip()

    # Must have @digest
    if "@" not in ref:
        issues.append(PinningIssue(
            "ERROR", image_ref,
            f"Docker image '{image_ref}' has no SHA-256 digest. "
            f"Pin to @sha256:... for immutable deployment."
        ))
        return issues

    digest = ref.split("@")[-1]
    if not SHA256_PATTERN.match(digest):
        issues.append(PinningIssue(
            "ERROR", image_ref,
            f"Docker image digest '{digest}' is not valid SHA-256 (expected 64 hex chars).",
        ))
        return issues

    return issues  # OK


def validate_gitlab_image(image_ref: str) -> List[PinningIssue]:
    """GitLab CI uses same image: directive as Docker. Same validation."""
    return validate_docker_image(image_ref)


def validate_github_workflow(workflow: dict) -> PinningResult:
    """
    Validate a GitHub Actions workflow YAML (parsed as dict).
    Checks all `uses:` and `container:`/`services:`.
    """
    issues = []
    pinned = 0
    mutable = 0

    jobs = workflow.get("jobs", {})
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue

        # 1. Container image (at job level)
        container = job.get("container", {})
        if isinstance(container, dict) and "image" in container:
            line = f"jobs.{job_name}.container.image"
            step_issues = validate_docker_image(container["image"])
            issues.extend([PinningIssue(i.severity, line, i.message) for i in step_issues])
            if step_issues:
                mutable += 1
            else:
                pinned += 1

        # 2. Services (at job level)
        services = job.get("services", {})
        if isinstance(services, dict):
            for svc_name, svc in services.items():
                if isinstance(svc, dict) and "image" in svc:
                    line = f"jobs.{job_name}.services.{svc_name}.image"
                    step_issues = validate_docker_image(svc["image"])
                    issues.extend([PinningIssue(i.severity, line, i.message) for i in step_issues])
                    if step_issues:
                        mutable += 1
                    else:
                        pinned += 1

        # 3. Steps (uses: directives)
        steps = job.get("steps", [])
        if isinstance(steps, list):
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if "uses" in step:
                    line = f"jobs.{job_name}.steps[{i}].uses"
                    step_issues = validate_github_action(f"uses: {step['uses']}")
                    issues.extend([PinningIssue(i.severity, line, i.message) for i in step_issues])
                    if step_issues:
                        mutable += 1
                    else:
                        pinned += 1

    return PinningResult(
        is_valid=not any(i.severity == "ERROR" for i in issues),
        issues=issues,
        pinned_count=pinned,
        mutable_count=mutable,
    )


def validate_gitlab_ci(config: dict) -> PinningResult:
    """
    Validate a .gitlab-ci.yml config (parsed as dict).
    Checks `image:` directive and `services:`.
    """
    issues = []
    pinned = 0
    mutable = 0

    # Global image
    if "image" in config:
        step_issues = validate_gitlab_image(config["image"])
        issues.extend([PinningIssue("ERROR", "image", i.message) for i in step_issues])
        if step_issues:
            mutable += 1
        else:
            pinned += 1

    # Per-job images
    for job_name, job in config.items():
        if not isinstance(job, dict):
            continue
        if "image" in job:
            step_issues = validate_gitlab_image(job["image"])
            issues.extend([PinningIssue("ERROR", f"jobs.{job_name}.image", i.message) for i in step_issues])
            if step_issues:
                mutable += 1
            else:
                pinned += 1

        # Services
        services = job.get("services", [])
        if isinstance(services, list):
            for i, svc in enumerate(services):
                if isinstance(svc, dict) and "image" in svc:
                    step_issues = validate_gitlab_image(svc["image"])
                    issues.extend([PinningIssue("ERROR", f"jobs.{job_name}.services[{i}].image", i.message) for i in step_issues])
                    if step_issues:
                        mutable += 1
                    else:
                        pinned += 1

    return PinningResult(
        is_valid=not any(i.severity == "ERROR" for i in issues),
        issues=issues,
        pinned_count=pinned,
        mutable_count=mutable,
    )


def validate_workflow_file(path: str, kind: str = "github") -> PinningResult:
    """Load and validate a workflow file."""
    import yaml
    with open(path) as f:
        config = yaml.safe_load(f) or {}
    if kind == "github":
        return validate_github_workflow(config)
    elif kind == "gitlab":
        return validate_gitlab_ci(config)
    else:
        return PinningResult(
            is_valid=False,
            issues=[PinningIssue("ERROR", "kind", f"Unknown kind '{kind}'")],
        )


# === Secret detection in CI/CD ===

# Patterns that indicate hardcoded secrets in CI files
SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{20,}'), "API key/secret"),
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS access key"),
    (re.compile(r'-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----'), "Private key"),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), "GitHub personal token"),
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), "OpenAI/Stripe API key"),
    (re.compile(r'xox[baprs]-[A-Za-z0-9-]{10,}'), "Slack token"),
]


def detect_secrets_in_workflow(workflow_text: str) -> List[PinningIssue]:
    """Detect hardcoded secrets in CI/CD workflow text."""
    issues = []
    for pattern, kind in SECRET_PATTERNS:
        for match in pattern.finditer(workflow_text):
            issues.append(PinningIssue(
                "ERROR", f"line ~{workflow_text[:match.start()].count(chr(10))+1}",
                f"Hardcoded {kind} detected. Use ${{ secrets.NAME }} instead.",
            ))
    return issues
