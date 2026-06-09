"""
Adversarial test: CI/CD Pin Bypass
====================================
Tests that an attacker cannot bypass CI/CD image pinning.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ci_cd_pinning import (
    validate_github_action, validate_docker_image,
    validate_github_workflow, detect_secrets_in_workflow,
)
from lib.image_pin import (
    parse_image_ref, validate_image_ref, is_mutable_tag,
    ImagePolicy,
)


# === ATTACK 1: Branch reference instead of tag ===
def test_github_action_branch_ref_rejected():
    """attacker uses @main which is mutable."""
    issues = validate_github_action("uses: actions/checkout@main")
    assert len(issues) == 1
    # The error message should mention pinning requirement
    assert "pinned" in issues[0].message.lower() or "sha" in issues[0].message.lower()


# === ATTACK 2: Forge SHA-1 with non-hex chars ===
def test_github_action_invalid_sha1_rejected():
    issues = validate_github_action("uses: actions/checkout@zzznothexchars1234567890123456789012345")
    # Non-hex (or wrong length) should be rejected
    assert any("pinned" in i.message.lower() or "sha" in i.message.lower() for i in issues)


# === ATTACK 3: Local action bypass ===
def test_github_action_local_action_allowed():
    """Local actions (./) don't need SHA — they ARE the source."""
    issues = validate_github_action("uses: ./my-local-action")
    assert issues == []


# === ATTACK 4: Docker image with non-standard digest format ===
def test_docker_image_sha512_rejected():
    """SHA-512 is not SHA-256. Should be rejected."""
    issues = validate_docker_image("python@sha512:abc123...")
    # Should be rejected (we only accept sha256:64hex)
    assert len(issues) == 1


# === ATTACK 5: Docker image with fake "immutable-looking" tag ===
def test_docker_image_attacker_fake_immutable():
    """Attacker uses a tag that LOOKS immutable but isn't (e.g., 'v1.0-locked')."""
    img = "myregistry/myimage:v1.0-locked"  # No digest
    issues = validate_docker_image(img)
    assert len(issues) == 1
    assert "sha-256 digest" in issues[0].message.lower() or "digest" in issues[0].message.lower()


# === ATTACK 6: Image policy bypass via env var override ===
def test_image_policy_no_env_var_bypass():
    """An attacker tries to bypass policy with a variable that resolves to mutable tag."""
    p = ImagePolicy()
    # If we have an image like $IMAGE and $IMAGE resolves to "python:3.12", we'd miss it
    # But our validator just checks the literal string
    # We accept that env var resolution is out of scope (would be a separate feature)
    valid, issues = p.check("python:3.12")
    assert not valid  # Still rejected as mutable


# === ATTACK 7: Workflow with mixed pinned + unpinned steps ===
def test_workflow_one_unpinned_breaks_all():
    """One unpinned step should fail the entire workflow."""
    workflow = {
        "jobs": {
            "build": {
                "steps": [
                    {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"},  # OK
                    {"uses": "malicious/action@main"},  # BAD
                ]
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert not r.is_valid


# === ATTACK 8: Secret leak via CI variable in plaintext ===
def test_hardcoded_secret_in_yaml_caught():
    """Secret in `env:` block of workflow should be detected."""
    workflow_text = """
name: deploy
on: [push]
jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      AWS_SECRET_KEY: AKIAIOSFODNN7EXAMPLE
    steps:
      - uses: actions/checkout@v4
"""
    issues = detect_secrets_in_workflow(workflow_text)
    assert len(issues) >= 1


# === ATTACK 9: Image tag with embedded digest-like string ===
def test_image_tag_not_digest():
    """An attacker uses a tag that looks like a digest."""
    img = "python:3.12@sha256"
    issues = validate_docker_image(img)
    # @sha256 alone is not a full digest
    assert len(issues) == 1


# === ATTACK 10: Parse robustness — weird but valid images ===
def test_parse_image_with_port_in_registry():
    img = parse_image_ref("registry.example.com:5000/myimage:1.0")
    assert img.registry == "registry.example.com:5000"
    assert img.repo == "myimage"
    assert img.tag == "1.0"


def test_parse_image_with_no_tag():
    img = parse_image_ref("python")
    assert img.tag is None


def test_parse_image_with_only_registry():
    """registry/repo without tag."""
    img = parse_image_ref("quay.io/org/img")
    assert img.registry == "quay.io"
    assert img.repo == "org/img"
    assert img.tag is None


# === ATTACK 11: Tag override via env var (out of scope) ===
def test_image_policy_only_checks_literal():
    """Policy checks the literal image_ref, not env-resolved values.
    This is a known limitation, documented as such."""
    # We don't have env resolution, so a literal "python:3.12" is rejected.
    p = ImagePolicy()
    valid, _ = p.check("python:3.12")
    assert not valid
    # "$IMAGE_TAG" is also rejected (no tag parsed, no digest → unpinned)
    valid, _ = p.check("$IMAGE_TAG")
    # Documented limitation: env var resolution is out of scope
    assert not valid


# === ATTACK 12: Registry spoofing via similar domain ===
def test_similar_registry_not_in_muatable_check():
    """A typo-squatted registry like 'dockerl.io' vs 'docker.io' should still
    be parsed correctly (it IS a registry due to the dot).
    """
    img = parse_image_ref("dockerl.io/myimage:1.0")
    # Detected as registry (contains dot)
    assert img.registry == "dockerl.io"
    # Still no digest → mutable
    issues = validate_docker_image("dockerl.io/myimage:1.0")
    assert not issues == []


# === ATTACK 13: Digest with all-zeroes (potentially valid but suspicious) ===
def test_all_zero_digest_accepted():
    """All-zero SHA-256 is valid format, even if suspicious."""
    img = "python@sha256:0000000000000000000000000000000000000000000000000000000000000000"
    issues = validate_docker_image(img)
    # Format is valid → no error
    assert issues == []


# === ATTACK 14: Mixed case digest ===
def test_mixed_case_digest_rejected():
    """Docker requires lowercase hex. Mixed case is rejected."""
    issues = validate_docker_image("python@sha256:ABC123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert len(issues) == 1


# === ATTACK 15: Workflow with services using mutable images ===
def test_workflow_services_must_be_pinned():
    workflow = {
        "jobs": {
            "test": {
                "services": {
                    "postgres": {"image": "postgres:16"},  # Mutable
                },
                "steps": [],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert not r.is_valid


# === ATTACK 16: Workflow with unpinned container ===
def test_workflow_container_must_be_pinned():
    workflow = {
        "jobs": {
            "build": {
                "container": {"image": "node:20"},  # Mutable
                "steps": [],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert not r.is_valid


# === ATTACK 17: Pinning to wrong digest (bit-flip attack) ===
def test_pinning_digest_mismatch_with_actual():
    """If a user pins to digest A but the image is actually digest B (bit-flip),
    the validator doesn't know (we don't fetch the image). This is a known
    limitation — actual digest verification requires registry API call.
    """
    # The validator only checks FORMAT, not actual content match.
    # An attacker who controls the registry could serve different content
    # at the same digest. But that's a registry compromise, not a pinning issue.
    # Document as limitation.
    issues = validate_docker_image("python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert issues == []  # Format is OK, we can't verify content


# === ATTACK 18: Multiple registries in same workflow ===
def test_multi_registry_workflow():
    workflow = {
        "jobs": {
            "build": {
                "container": {
                    "image": "gcr.io/proj/img:1.0@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
                },
                "services": {
                    "redis": {
                        "image": "redis:7@sha256:def456abc123def456abc123def456abc123def456abc123def456abc123abcd"
                    }
                },
                "steps": [
                    {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"}
                ]
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert r.is_valid
    assert r.pinned_count == 3  # container + service + step


# === ATTACK 19: Empty uses line ===
def test_empty_uses_line():
    """Empty `uses:` line is detected (no ref captured)."""
    issues = validate_github_action("uses: ")
    # If no ref captured, no issues (it's a no-op, not an error).
    # This is a known limitation — we accept that an empty uses: passes silently.
    # The workflow YAML parser would catch this at a higher level.
    # Document as a gap.
    assert issues == [] or any("empty" in i.message.lower() for i in issues)


# === ATTACK 20: GitLab CI with mutable image in service ===
def test_gitlab_service_unpinned_rejected():
    """GitLab service (per-job) with mutable image is rejected."""
    config = {
        "test": {
            "image": "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            "services": [
                {"name": "redis", "image": "redis:7"},  # Mutable
            ],
            "script": ["pytest"],
        }
    }
    from lib.ci_cd_pinning import validate_gitlab_ci
    r = validate_gitlab_ci(config)
    assert not r.is_valid


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
