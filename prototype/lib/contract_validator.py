"""
QW8 — Contract Validator (OpenAPI / AsyncAPI)
================================================
Validate that OpenAPI/AsyncAPI contracts are well-formed and reject
hidden endpoints/events. Closes: Contract poisoning (hidden backdoor).
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


# Required fields for OpenAPI 3.x
OPENAPI_REQUIRED_TOP = {"openapi", "info", "paths"}
OPENAPI_REQUIRED_INFO = {"title", "version"}
OPENAPI_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}

# Required fields for AsyncAPI 2.x / 3.x
ASYNCAPI_REQUIRED_TOP = {"asyncapi", "info", "channels"}  # 2.x
# AsyncAPI 3.x uses 'channels' too but operations structure differs
ASYNCAPI_HTTP_METHODS = {"subscribe", "publish"}


@dataclass
class ContractIssue:
    """A contract validation issue."""
    severity: str  # "ERROR" | "WARN"
    location: str
    message: str


@dataclass
class ContractResult:
    is_valid: bool
    issues: List[ContractIssue]
    endpoint_count: int = 0
    channel_count: int = 0


def validate_openapi(spec: dict) -> ContractResult:
    """Validate an OpenAPI 3.x spec. Reject hidden endpoints, missing required fields."""
    issues = []

    # Top-level
    missing_top = OPENAPI_REQUIRED_TOP - set(spec.keys())
    if missing_top:
        issues.append(ContractIssue("ERROR", "root", f"Missing top-level fields: {missing_top}"))

    if "openapi" in spec:
        v = spec["openapi"]
        if not isinstance(v, str) or not v.startswith("3."):
            issues.append(ContractIssue("ERROR", "openapi", f"Only OpenAPI 3.x supported, got {v}"))

    # Info
    if "info" in spec:
        info = spec["info"]
        missing_info = OPENAPI_REQUIRED_INFO - set(info.keys())
        if missing_info:
            issues.append(ContractIssue("ERROR", "info", f"Missing info fields: {missing_info}"))
        # No contact with PII allowed
        if "contact" in info and "email" in info["contact"]:
            email = info["contact"]["email"]
            if not re.match(r"^[\w.+-]+@example\.com$", email):
                issues.append(ContractIssue(
                    "WARN", "info.contact.email",
                    f"Contact email '{email}' is not a placeholder (e.g., contact@example.com). "
                    f"May leak real PII."
                ))

    # Paths / endpoints
    paths = spec.get("paths", {})
    endpoint_count = 0
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        if not path.startswith("/"):
            issues.append(ContractIssue("ERROR", path, f"Path must start with /, got '{path}'"))
        # Path traversal
        if ".." in path or "//" in path:
            issues.append(ContractIssue("ERROR", path, f"Path contains traversal or double-slash"))
        for method, operation in methods.items():
            if method.lower() not in OPENAPI_HTTP_METHODS:
                issues.append(ContractIssue(
                    "ERROR", f"{path}.{method}",
                    f"Unknown HTTP method '{method}'"
                ))
                continue
            endpoint_count += 1
            # Check responses
            if "responses" not in operation:
                issues.append(ContractIssue(
                    "ERROR", f"{path}.{method}",
                    f"Missing 'responses' field"
                ))
            # No hidden internal endpoints (heuristic)
            if "internal" in path.lower() and "x-internal" not in operation:
                issues.append(ContractIssue(
                    "WARN", f"{path}.{method}",
                    f"Path contains 'internal' but no x-internal marker"
                ))

    return ContractResult(
        is_valid=not any(i.severity == "ERROR" for i in issues),
        issues=issues,
        endpoint_count=endpoint_count,
    )


def validate_asyncapi(spec: dict) -> ContractResult:
    """Validate an AsyncAPI 2.x / 3.x spec."""
    issues = []
    # Top-level
    if "asyncapi" not in spec:
        issues.append(ContractIssue("ERROR", "root", "Missing 'asyncapi' version field"))

    version = spec.get("asyncapi", "")
    if not (version.startswith("2.") or version.startswith("3.")):
        issues.append(ContractIssue("ERROR", "asyncapi", f"Only AsyncAPI 2.x/3.x supported, got {version}"))

    # Info
    if "info" in spec:
        info = spec["info"]
        missing_info = OPENAPI_REQUIRED_INFO - set(info.keys())
        if missing_info:
            issues.append(ContractIssue("ERROR", "info", f"Missing info fields: {missing_info}"))

    # Channels (2.x style)
    channels = spec.get("channels", {})
    channel_count = 0
    if isinstance(channels, dict):
        for channel_name, channel_def in channels.items():
            if not isinstance(channel_def, dict):
                continue
            channel_count += 1
            # Must have publish or subscribe
            if "publish" not in channel_def and "subscribe" not in channel_def:
                issues.append(ContractIssue(
                    "ERROR", f"channels.{channel_name}",
                    "Channel must have 'publish' or 'subscribe' operation"
                ))
            # Check operations
            for op_type in ("publish", "subscribe"):
                if op_type not in channel_def:
                    continue
                op = channel_def[op_type]
                if "message" not in op:
                    issues.append(ContractIssue(
                        "ERROR", f"channels.{channel_name}.{op_type}",
                        "Operation missing 'message' field"
                    ))

    return ContractResult(
        is_valid=not any(i.severity == "ERROR" for i in issues),
        issues=issues,
        channel_count=channel_count,
    )


def load_and_validate(path: str, kind: str = "openapi") -> ContractResult:
    """Load a contract file and validate it."""
    with open(path) as f:
        if path.endswith(".yaml") or path.endswith(".yml"):
            try:
                import yaml
                spec = yaml.safe_load(f)
            except ImportError:
                # Fallback to JSON
                spec = json.loads(f.read() or "{}")
        else:
            spec = json.load(f)

    if kind == "openapi":
        return validate_openapi(spec)
    elif kind == "asyncapi":
        return validate_asyncapi(spec)
    else:
        return ContractResult(
            is_valid=False,
            issues=[ContractIssue("ERROR", "kind", f"Unknown kind '{kind}', expected 'openapi' or 'asyncapi'")],
        )


def check_no_hidden_endpoints(spec: dict) -> List[ContractIssue]:
    """Detect potential hidden backdoor endpoints."""
    issues = []
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            # Backdoor: operation with no security defined
            if method.lower() in OPENAPI_HTTP_METHODS:
                if "security" not in op and "security" not in spec:
                    issues.append(ContractIssue(
                        "WARN", f"{path}.{method}",
                        "No security defined (potential unauthenticated backdoor)"
                    ))
            # Backdoor: POST/PUT/DELETE with no body validation
            if method.lower() in ("post", "put", "patch"):
                if "requestBody" not in op:
                    issues.append(ContractIssue(
                        "WARN", f"{path}.{method}",
                        f"{method.upper()} without requestBody validation"
                    ))
    return issues
