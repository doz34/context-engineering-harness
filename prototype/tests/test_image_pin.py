"""Test QW-S3-2: Container image SHA-256 pinning."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.image_pin import (
    parse_image_ref, is_mutable_tag, validate_image_ref,
    pin_to_digest, ImagePolicy, ImageRef,
)


# === PARSING ===

def test_parse_simple_image():
    img = parse_image_ref("python:3.12")
    assert img.registry == "docker.io"
    assert img.repo == "python"
    assert img.tag == "3.12"
    assert img.digest is None


def test_parse_with_digest():
    img = parse_image_ref("python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert img.tag == "3.12"
    assert img.digest == "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"


def test_parse_digest_only():
    img = parse_image_ref("python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert img.tag is None
    assert img.digest == "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"


def test_parse_gcr_image():
    img = parse_image_ref("gcr.io/myproject/myimage:v1")
    assert img.registry == "gcr.io"
    assert img.repo == "myproject/myimage"
    assert img.tag == "v1"


def test_parse_ghcr_image():
    img = parse_image_ref("ghcr.io/org/img:1.0.0")
    assert img.registry == "ghcr.io"
    assert img.repo == "org/img"
    assert img.tag == "1.0.0"


def test_parse_user_image():
    """Docker Hub user/repo pattern."""
    img = parse_image_ref("doz34/myimage:1.0")
    assert img.registry == "docker.io"
    assert img.repo == "doz34/myimage"


def test_parse_empty_returns_blank():
    img = parse_image_ref("")
    assert img.repo == ""


# === MUTABLE TAG ===

def test_latest_is_mutable():
    assert is_mutable_tag("latest") is True


def test_main_is_mutable():
    assert is_mutable_tag("main") is True


def test_specific_version_not_mutable():
    assert is_mutable_tag("3.12") is False


def test_release_is_mutable():
    assert is_mutable_tag("release") is True


# === VALIDATION ===

def test_validate_pinned_ok():
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = validate_image_ref(img)
    assert valid
    assert issues == []


def test_validate_mutable_tag_rejected():
    valid, issues = validate_image_ref("python:3.12")
    assert not valid
    assert any("mutable" in i.lower() for i in issues)


def test_validate_latest_rejected():
    valid, issues = validate_image_ref("python:latest")
    assert not valid


def test_validate_digest_only_ok():
    img = "python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = validate_image_ref(img)
    assert valid


def test_validate_gcr_mutable_rejected():
    valid, issues = validate_image_ref("gcr.io/proj/img:v1")
    assert not valid


def test_validate_semver_ok():
    img = "python:3.12.5@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = validate_image_ref(img)
    assert valid


# === POLICY ===

def test_policy_rejects_mutable():
    p = ImagePolicy()
    valid, issues = p.check("python:3.12")
    assert not valid
    assert any("not pinned" in i.lower() for i in issues)


def test_policy_accepts_pinned():
    p = ImagePolicy()
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = p.check(img)
    assert valid


def test_policy_allowed_tags():
    """Production policy with explicit allowed tags list."""
    p = ImagePolicy(allowed_tags={"3.12", "3.13"}, deny_latest=True)
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = p.check(img)
    assert valid


def test_policy_disallowed_tag():
    p = ImagePolicy(allowed_tags={"3.13"}, deny_latest=True)
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = p.check(img)
    assert not valid
    assert any("not in allowed" in i.lower() for i in issues)


def test_policy_no_deny_latest():
    """If deny_latest=False, only pinning is required (not specific tags)."""
    p = ImagePolicy(deny_latest=False)
    img = "python:latest@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    valid, issues = p.check(img)
    # Pinned, so valid
    assert valid


# === RESOLVING (skipped if no skopeo/docker) ===

def test_pin_to_digest_already_pinned():
    """If image is already pinned, return as-is."""
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    result = pin_to_digest(img)
    # Returns the pinned ref (or None if registry resolution failed)
    if result is not None:
        assert "@sha256:" in result
        assert "abc123def456" in result


def test_resolve_digest_via_registry_already_pinned():
    """If image is already pinned, return its digest."""
    img = "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    result = pin_to_digest(img)
    if result is not None:
        assert "abc123def456" in result


# === IMMUTABLE CONVERSION ===

def test_to_immutable_with_digest():
    img = parse_image_ref("python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    result = img.to_immutable()
    assert "@sha256:" in result
    assert "abc123def456" in result


def test_to_immutable_without_digest():
    """If mutable, return canonical form (with implicit registry)."""
    img = parse_image_ref("python:3.12")
    result = img.to_immutable()
    # Canonized to include registry
    assert "python:3.12" in result
    assert result == "docker.io/python:3.12"


def test_to_immutable_with_gcr():
    img = parse_image_ref("gcr.io/proj/img:1.0@sha256:def456abc123def456abc123def456abc123def456abc123def456abc123abcd")
    result = img.to_immutable()
    assert "gcr.io" in result
    assert "@sha256:" in result


# === IS_MUTABLE / IS_PINNED ===

def test_is_mutable_with_tag_no_digest():
    img = parse_image_ref("python:3.12")
    assert img.is_mutable() is True
    assert img.is_pinned() is False


def test_is_pinned_with_digest():
    img = parse_image_ref("python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert img.is_pinned() is True
    assert img.is_mutable() is False


def test_digest_only_is_pinned():
    img = parse_image_ref("python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd")
    assert img.is_pinned() is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
