"""Test QW-S3-1: CI/CD pipeline pinning."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ci_cd_pinning import (
    is_pinned_digest, is_mutable_tag,
    validate_github_action, validate_docker_image,
    validate_github_workflow, validate_gitlab_ci,
    detect_secrets_in_workflow, PinningResult,
)


# === MUTABLE TAG DETECTION ===

def test_latest_is_mutable():
    assert is_mutable_tag("latest") is True


def test_main_is_mutable():
    assert is_mutable_tag("main") is True


def test_semver_is_not_mutable():
    """v1.2.3 tags are convention-only mutable but accepted practice."""
    assert is_mutable_tag("v1.2.3") is False


def test_date_is_not_mutable():
    assert is_mutable_tag("20240101") is False


def test_unknown_is_not_mutable():
    assert is_mutable_tag("my-custom-tag") is False


# === SHA-256 DIGEST DETECTION ===

def test_valid_sha256_digest():
    ref = "python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    assert is_pinned_digest(ref) is True


def test_image_without_digest():
    assert is_pinned_digest("python:3.12") is False


def test_image_with_short_digest():
    """64 hex chars required."""
    ref = "python@sha256:abc123"
    assert is_pinned_digest(ref) is False


def test_image_with_uppercase_digest():
    """SHA-256 should be lowercase."""
    ref = "python@sha256:ABC123DEF456ABC123DEF456ABC123DEF456ABC123ABC123ABC123ABC123AB"
    assert is_pinned_digest(ref) is False


# === GITHUB ACTIONS ===

def test_github_action_pinned_ok():
    issues = validate_github_action("uses: actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e")
    assert issues == []


def test_github_action_mutable_tag_rejected():
    issues = validate_github_action("uses: actions/checkout@v4")
    assert len(issues) == 1
    assert issues[0].severity == "ERROR"
    # Either 'mutable' or 'sha pinned' is acceptable
    msg = issues[0].message.lower()
    assert "mutable" in msg or "sha pinned" in msg or "pinned" in msg


def test_github_action_branch_rejected():
    issues = validate_github_action("uses: actions/checkout@main")
    assert len(issues) == 1
    assert "main" in issues[0].message.lower() or "mutable" in issues[0].message.lower()


def test_github_action_no_version_rejected():
    issues = validate_github_action("uses: actions/checkout")
    # No version at all — should be rejected
    assert len(issues) >= 1


def test_github_action_local_action():
    issues = validate_github_action("uses: ./my-action")
    # Local action — should be allowed
    assert issues == []


# === DOCKER IMAGES ===

def test_docker_image_pinned_ok():
    img = "python@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    issues = validate_docker_image(img)
    assert issues == []


def test_docker_image_with_registry_pinned():
    img = "gcr.io/myproject/myimage@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
    issues = validate_docker_image(img)
    assert issues == []


def test_docker_image_mutable_tag_rejected():
    issues = validate_docker_image("python:3.12")
    assert len(issues) == 1
    assert "no sha-256 digest" in issues[0].message.lower()


def test_docker_image_latest_rejected():
    issues = validate_docker_image("python:latest")
    assert len(issues) == 1


def test_docker_image_no_tag_rejected():
    issues = validate_docker_image("python")
    assert len(issues) == 1


def test_docker_image_invalid_digest_rejected():
    """Digest with non-hex characters is rejected."""
    issues = validate_docker_image("python@sha256:zzzzz")
    assert len(issues) == 1


def test_docker_image_short_digest_rejected():
    issues = validate_docker_image("python@sha256:abc123")
    assert len(issues) == 1


# === FULL WORKFLOW VALIDATION ===

def test_github_workflow_pinned_ok():
    workflow = {
        "name": "CI",
        "on": ["push"],
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"},
                    {"uses": "actions/setup-python@a1b2c3d4e5f6071829a1b2c3d4e5f6071829a1b2"},
                ],
            }
        }
    }
    r = validate_github_workflow(workflow)
    # Each SHA is 40 chars (SHA-1) — both pinned
    assert r.is_valid
    assert r.pinned_count == 2
    assert r.mutable_count == 0


def test_github_workflow_mixed_pinning():
    workflow = {
        "jobs": {
            "build": {
                "steps": [
                    {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"},  # OK
                    {"uses": "actions/checkout@v4"},  # mutable
                ],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert not r.is_valid
    assert r.mutable_count == 1
    assert r.pinned_count == 1


def test_github_workflow_container_image_pinned():
    workflow = {
        "jobs": {
            "build": {
                "container": {
                    "image": "node:20@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
                },
                "steps": [],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert r.is_valid
    assert r.pinned_count == 1


def test_github_workflow_service_pinned():
    workflow = {
        "jobs": {
            "test": {
                "services": {
                    "postgres": {
                        "image": "postgres:16@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"
                    }
                },
                "steps": [],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert r.is_valid


def test_github_workflow_service_unpinned():
    workflow = {
        "jobs": {
            "test": {
                "services": {
                    "postgres": {"image": "postgres:16"}  # No digest
                },
                "steps": [],
            }
        }
    }
    r = validate_github_workflow(workflow)
    assert not r.is_valid


# === GITLAB CI ===

def test_gitlab_ci_pinned_ok():
    config = {
        "image": "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        "test": {
            "script": ["pytest"],
        }
    }
    r = validate_gitlab_ci(config)
    assert r.is_valid


def test_gitlab_ci_mutable_rejected():
    config = {
        "image": "python:3.12",  # No digest
    }
    r = validate_gitlab_ci(config)
    assert not r.is_valid


def test_gitlab_ci_per_job_image():
    config = {
        "test:python": {
            "image": "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            "script": ["pytest"],
        },
        "test:node": {
            "image": "node:20@sha256:def456abc123def456abc123def456abc123def456abc123def456abc123abcd",
            "script": ["npm test"],
        },
    }
    r = validate_gitlab_ci(config)
    assert r.is_valid
    assert r.pinned_count == 2


def test_gitlab_ci_with_services():
    config = {
        "image": "python:3.12@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
        "services": [
            {"name": "postgres", "image": "postgres:16@sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abcd"},
        ],
        "test": {"script": ["pytest"]},
    }
    r = validate_gitlab_ci(config)
    assert r.is_valid


# === SECRET DETECTION ===

def test_detect_aws_key():
    text = "AWS_ACCESS_KEY: AKIAIOSFODNN7EXAMPLE"
    issues = detect_secrets_in_workflow(text)
    assert len(issues) == 1
    assert "aws" in issues[0].message.lower()


def test_detect_github_token():
    text = "GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    issues = detect_secrets_in_workflow(text)
    # Could match both 'api_key/secret' pattern AND 'GitHub personal token' pattern
    assert len(issues) >= 1
    # Verify at least one mentions GitHub
    assert any("github" in i.message.lower() for i in issues)


def test_detect_openai_key():
    text = "API_KEY=sk-proj1234567890abcdefghij"
    issues = detect_secrets_in_workflow(text)
    assert len(issues) >= 1


def test_detect_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----"
    issues = detect_secrets_in_workflow(text)
    assert len(issues) == 1


def test_no_secrets_in_clean_workflow():
    text = """
    name: CI
    on: [push]
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@b4ffde4
    """
    issues = detect_secrets_in_workflow(text)
    assert issues == []


# === END-TO-END FILE VALIDATION ===

def test_validate_github_workflow_file():
    """End-to-end: load and validate a GitHub workflow YAML file.

    Skips cleanly when pyyaml is not installed (yaml is an optional dep
    in ci_cd_pinning — the rest of the test suite must work stdlib-only).
    """
    pytest = __import__("pytest")
    yaml = pytest.importorskip("yaml")
    with tempfile.TemporaryDirectory() as d:
        wf_path = os.path.join(d, "workflow.yml")
        wf_content = {
            "name": "CI",
            "on": ["push"],
            "jobs": {
                "build": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@b4ffde4f2a3e3b6c8c5e2e3b6c8c5e2e3b6c8c5e"},
                    ],
                }
            }
        }
        with open(wf_path, "w") as f:
            yaml.dump(wf_content, f)

        with open(wf_path) as f:
            config = yaml.safe_load(f)
        r = validate_github_workflow(config)
        assert r.is_valid


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
