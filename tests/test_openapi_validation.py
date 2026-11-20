"""
tests/test_openapi_validation.py
──────────────────────────────────
Quick validation suite confirming that orchestrate/openapi_spec.yaml:

  1. Parses cleanly as valid YAML.
  2. Declares OpenAPI version 3.0.x.
  3. Contains unique snake_case operationIds on every path/method.
  4. Has a non-empty description on every path operation.
  5. Has an x-ibm-nl-intent annotation on every path operation.
  6. Includes all eight expected skill operationIds.
  7. Has a valid global security block requiring ApiKeyAuth.
  8. Has required component schemas for all new endpoints.
  9. All new paths (/documents/analyze, /registry/sync,
     /registry/changelog, /registry/list) are present.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).parent.parent
_SPEC_PATH = _REPO_ROOT / "orchestrate" / "openapi_spec.yaml"

# All expected operationIds (snake_case, one per path/method)
_EXPECTED_OPERATION_IDS = {
    "clinical_query",
    "medication_check",
    "get_consent_document",
    "analyze_document",
    "get_dashboard_metrics",
    "sync_registry_bulletin",
    "get_registry_changelog",
    "get_registry_list",
}

# All expected paths
_EXPECTED_PATHS = {
    "/agent/query",
    "/registry/check",
    "/documents/{doc_type}/{language}",
    "/documents/analyze",
    "/analytics/dashboard",
    "/registry/sync",
    "/registry/changelog",
    "/registry/list",
}

# Required component schemas
_REQUIRED_SCHEMAS = {
    "AgentQueryRequest",
    "AgentQueryResponse",
    "AgentEscalatedResponse",
    "RegistryCheckResponse",
    "DocumentResponse",
    "DashboardResponse",
    "DocumentAnalyzeResponse",
    "RegistrySyncRequest",
    "RegistrySyncResponse",
    "ChangelogEntry",
    "ChangelogResponse",
    "ProactiveRecommendation",
    "RegistryListResponse",
}

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def spec() -> dict:
    """Load and return the parsed OpenAPI spec (module-scoped — load once)."""
    assert _SPEC_PATH.exists(), f"OpenAPI spec not found at {_SPEC_PATH}"
    with _SPEC_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def all_operations(spec) -> list[tuple[str, str, dict]]:
    """Return a flat list of (path, method, operation_dict) for every operation."""
    ops = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in _HTTP_METHODS and isinstance(operation, dict):
                ops.append((path, method.upper(), operation))
    return ops


# ══════════════════════════════════════════════════════════════════════════════
# 1. Basic structure
# ══════════════════════════════════════════════════════════════════════════════

class TestBasicStructure:

    def test_yaml_parses_cleanly(self, spec):
        """The spec must load as a non-empty dict."""
        assert isinstance(spec, dict)
        assert len(spec) > 0

    def test_openapi_version_is_3_0(self, spec):
        """Must declare OpenAPI 3.0.x."""
        version = spec.get("openapi", "")
        assert version.startswith("3.0"), f"Expected OpenAPI 3.0.x, got {version!r}"

    def test_info_block_has_title_and_version(self, spec):
        info = spec.get("info", {})
        assert "title" in info, "Missing info.title"
        assert "version" in info, "Missing info.version"
        assert len(info["title"]) > 0
        assert len(info["version"]) > 0

    def test_server_block_present(self, spec):
        servers = spec.get("servers", [])
        assert len(servers) >= 1
        assert any("localhost:8000" in s.get("url", "") for s in servers)

    def test_global_security_requires_api_key(self, spec):
        security = spec.get("security", [])
        assert any("ApiKeyAuth" in s for s in security), (
            "Global security must require ApiKeyAuth"
        )

    def test_api_key_security_scheme_present(self, spec):
        scheme = (
            spec.get("components", {})
            .get("securitySchemes", {})
            .get("ApiKeyAuth", {})
        )
        assert scheme.get("type") == "apiKey"
        assert scheme.get("in") == "header"
        assert scheme.get("name") == "X-API-Key"


# ══════════════════════════════════════════════════════════════════════════════
# 2. All expected paths present
# ══════════════════════════════════════════════════════════════════════════════

class TestPaths:

    def test_all_expected_paths_present(self, spec):
        paths = set(spec.get("paths", {}).keys())
        missing = _EXPECTED_PATHS - paths
        assert not missing, f"Missing paths in spec: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. operationId: unique, snake_case, complete
# ══════════════════════════════════════════════════════════════════════════════

class TestOperationIds:

    def test_all_operations_have_operation_id(self, all_operations):
        for path, method, op in all_operations:
            assert "operationId" in op, (
                f"Missing operationId on {method} {path}"
            )

    def test_all_operation_ids_are_snake_case(self, all_operations):
        for path, method, op in all_operations:
            op_id = op.get("operationId", "")
            assert _SNAKE_CASE_RE.match(op_id), (
                f"operationId {op_id!r} on {method} {path} is not snake_case"
            )

    def test_operation_ids_are_unique(self, all_operations):
        ids = [op.get("operationId") for _, _, op in all_operations]
        assert len(ids) == len(set(ids)), (
            f"Duplicate operationIds found: "
            f"{[x for x in set(ids) if ids.count(x) > 1]}"
        )

    def test_all_expected_skill_ids_present(self, all_operations):
        ids = {op.get("operationId") for _, _, op in all_operations}
        missing = _EXPECTED_OPERATION_IDS - ids
        assert not missing, f"Missing operationIds: {missing}"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Descriptions and x-ibm-nl-intent on every operation
# ══════════════════════════════════════════════════════════════════════════════

class TestDescriptionsAndIntent:

    def test_all_operations_have_non_empty_description(self, all_operations):
        for path, method, op in all_operations:
            desc = op.get("description", "")
            assert len(desc.strip()) > 20, (
                f"description too short or missing on {method} {path}: {desc!r}"
            )

    def test_all_operations_have_x_ibm_nl_intent(self, all_operations):
        for path, method, op in all_operations:
            intent = op.get("x-ibm-nl-intent", "")
            assert len(str(intent).strip()) > 20, (
                f"x-ibm-nl-intent too short or missing on {method} {path}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Component schemas complete
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemas:

    def test_all_required_schemas_present(self, spec):
        schemas = set(
            spec.get("components", {}).get("schemas", {}).keys()
        )
        missing = _REQUIRED_SCHEMAS - schemas
        assert not missing, f"Missing component schemas: {missing}"
