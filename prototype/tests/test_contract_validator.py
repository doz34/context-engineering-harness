"""Test QW8: OpenAPI/AsyncAPI contract validator."""
import sys
import os
import tempfile
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.contract_validator import (
    validate_openapi, validate_asyncapi, load_and_validate,
    check_no_hidden_endpoints, ContractResult,
)


SAMPLE_OPENAPI_GOOD = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "summary": "List users",
                "responses": {"200": {"description": "OK"}}
            },
            "post": {
                "summary": "Create user",
                "requestBody": {"content": {"application/json": {}}},
                "responses": {"201": {"description": "Created"}}
            }
        }
    }
}


def test_validate_openapi_good():
    r = validate_openapi(SAMPLE_OPENAPI_GOOD)
    assert r.is_valid
    assert r.endpoint_count == 2


def test_validate_openapi_missing_top_level():
    spec = {"info": {}, "paths": {}}
    r = validate_openapi(spec)
    assert not r.is_valid
    assert any("openapi" in i.message for i in r.issues)


def test_validate_openapi_wrong_version():
    spec = dict(SAMPLE_OPENAPI_GOOD, **{"openapi": "2.0"})
    r = validate_openapi(spec)
    assert not r.is_valid


def test_validate_openapi_missing_info_fields():
    spec = dict(SAMPLE_OPENAPI_GOOD, **{"info": {}})
    r = validate_openapi(spec)
    assert not r.is_valid
    assert any("info" in i.location for i in r.issues)


def test_validate_openapi_path_must_start_with_slash():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "users": {"get": {"responses": {"200": {}}}}
        }
    }
    r = validate_openapi(spec)
    assert not r.is_valid


def test_validate_openapi_path_traversal():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/../etc/passwd": {"get": {"responses": {"200": {}}}}
        }
    }
    r = validate_openapi(spec)
    assert not r.is_valid
    assert any("traversal" in i.message for i in r.issues)


def test_validate_openapi_unknown_method():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/x": {"hijack": {"responses": {"200": {}}}}
        }
    }
    r = validate_openapi(spec)
    assert not r.is_valid
    assert any("Unknown HTTP method" in i.message for i in r.issues)


def test_validate_openapi_missing_responses():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/x": {"get": {}}
        }
    }
    r = validate_openapi(spec)
    assert not r.is_valid
    assert any("responses" in i.message for i in r.issues)


def test_pii_email_warning():
    spec = dict(SAMPLE_OPENAPI_GOOD)
    spec["info"]["contact"] = {"email": "real.person@company.com"}
    r = validate_openapi(spec)
    # WARN level, not blocking
    assert any("placeholder" in i.message for i in r.issues)


def test_placeholder_email_ok():
    spec = dict(SAMPLE_OPENAPI_GOOD)
    spec["info"]["contact"] = {"email": "contact@example.com"}
    r = validate_openapi(spec)
    # No warning
    assert not any("placeholder" in i.message for i in r.issues)


def test_validate_asyncapi_good():
    spec = {
        "asyncapi": "2.6.0",
        "info": {"title": "Events", "version": "1.0"},
        "channels": {
            "user/created": {
                "publish": {
                    "message": {"payload": {}}
                }
            }
        }
    }
    r = validate_asyncapi(spec)
    assert r.is_valid
    assert r.channel_count == 1


def test_validate_asyncapi_missing_version():
    spec = {
        "info": {"title": "T", "version": "1.0"},
        "channels": {}
    }
    r = validate_asyncapi(spec)
    assert not r.is_valid


def test_validate_asyncapi_wrong_version():
    spec = {"asyncapi": "1.0", "info": {}, "channels": {}}
    r = validate_asyncapi(spec)
    assert not r.is_valid


def test_validate_asyncapi_channel_no_publish_or_subscribe():
    spec = {
        "asyncapi": "2.6.0",
        "info": {"title": "T", "version": "1.0"},
        "channels": {
            "x": {}
        }
    }
    r = validate_asyncapi(spec)
    assert not r.is_valid


def test_validate_asyncapi_missing_message():
    spec = {
        "asyncapi": "2.6.0",
        "info": {"title": "T", "version": "1.0"},
        "channels": {
            "x": {"publish": {}}
        }
    }
    r = validate_asyncapi(spec)
    assert not r.is_valid


def test_load_and_validate_json_openapi():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "api.json")
        with open(path, "w") as f:
            json.dump(SAMPLE_OPENAPI_GOOD, f)
        r = load_and_validate(path, kind="openapi")
        assert r.is_valid


def test_load_and_validate_unknown_kind():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "api.json")
        with open(path, "w") as f:
            json.dump({}, f)
        r = load_and_validate(path, kind="graphql")
        assert not r.is_valid


def test_check_no_hidden_endpoints():
    """POST without security or body = potential backdoor."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "paths": {
            "/admin": {
                "post": {}  # No security, no body
            }
        }
    }
    issues = check_no_hidden_endpoints(spec)
    assert len(issues) >= 2  # No security + no body


def test_check_no_hidden_endpoints_with_security_ok():
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0"},
        "security": [{"bearerAuth": []}],
        "paths": {
            "/admin": {
                "post": {
                    "security": [{"bearerAuth": []}],
                    "requestBody": {"content": {}}
                }
            }
        }
    }
    issues = check_no_hidden_endpoints(spec)
    assert issues == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
