"""Tests for the MCP Tool Marketplace API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app

HEADERS_WITH_TOKEN = {
    "x-mainlayer-token": "tok_test",
    "x-vendor-id": "vendor-test-001",
}

SAMPLE_TOOL = {
    "name": "Test Analyser",
    "description": "A test tool for automated tests of the marketplace.",
    "price_usdc": 0.002,
    "category": "utilities",
    "tags": ["test", "demo"],
    "mcp_endpoint": "https://tools.example.com/mcp/test",
    "tool_schema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_mainlayer():
    """Bypass all Mainlayer network calls."""
    with (
        patch("src.main.charge_tool_install", new_callable=AsyncMock) as mock_charge,
        patch("src.billing.charge_agent", new_callable=AsyncMock) as mock_agent,
        patch("src.main.create_resource", new_callable=AsyncMock) as mock_res,
    ):
        mock_charge.return_value = {"id": "pay_mock_001", "status": "succeeded"}
        mock_agent.return_value = {"id": "pay_mock_001", "status": "succeeded"}
        mock_res.return_value = {"id": "res_mock_001", "status": "active", "mock": True}
        yield


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# List tools
# ---------------------------------------------------------------------------


def test_list_tools(client):
    resp = client.get("/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 5  # seed tools
    assert len(body["tools"]) >= 1


def test_list_tools_filter_by_category(client):
    resp = client.get("/tools", params={"category": "search"})
    assert resp.status_code == 200
    for tool in resp.json()["tools"]:
        assert tool["category"] == "search"


def test_list_tools_search(client):
    resp = client.get("/tools", params={"search": "calculator"})
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert any("Calculator" in t["name"] or "calculator" in t["description"].lower() for t in tools)


# ---------------------------------------------------------------------------
# Get tool
# ---------------------------------------------------------------------------


def test_get_tool_exists(client):
    resp = client.get("/tools/tool-web-search-001")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Web Search"


def test_get_tool_not_found(client):
    resp = client.get("/tools/nonexistent-tool-xyz")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def test_list_categories(client):
    resp = client.get("/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tools"] >= 5
    assert len(body["categories"]) >= 1


# ---------------------------------------------------------------------------
# Publish tool
# ---------------------------------------------------------------------------


def test_publish_tool_requires_token(client):
    resp = client.post("/tools", json=SAMPLE_TOOL)
    assert resp.status_code == 402


def test_publish_tool_with_token(client):
    resp = client.post("/tools", json=SAMPLE_TOOL, headers=HEADERS_WITH_TOKEN)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == SAMPLE_TOOL["name"]
    assert "id" in body


# ---------------------------------------------------------------------------
# Install tool
# ---------------------------------------------------------------------------


def test_install_tool(client):
    resp = client.post(
        "/tools/tool-web-search-001/install",
        json={"agent_api_key": "ak_test_agent", "quantity": 5},
        headers={"x-mainlayer-token": "tok_test"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tool_id"] == "tool-web-search-001"
    assert body["calls_remaining"] == 5
    assert "access_token" in body


def test_install_nonexistent_tool(client):
    resp = client.post(
        "/tools/does-not-exist/install",
        json={"agent_api_key": "ak_test"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Use tool
# ---------------------------------------------------------------------------


def test_use_tool(client):
    # Install first
    install_resp = client.post(
        "/tools/tool-web-search-001/install",
        json={"agent_api_key": "ak_test_agent", "quantity": 3},
    )
    assert install_resp.status_code == 200
    token = install_resp.json()["access_token"]

    # Use the tool
    use_resp = client.post(
        "/tools/tool-web-search-001/use",
        json={"access_token": token, "inputs": {"query": "test query"}},
    )
    assert use_resp.status_code == 200
    body = use_resp.json()
    assert body["success"] is True
    assert body["calls_remaining"] == 2


def test_use_tool_exhausted(client):
    install_resp = client.post(
        "/tools/tool-calculator-001/install",
        json={"agent_api_key": "ak_test_agent", "quantity": 1},
    )
    token = install_resp.json()["access_token"]

    # Use the 1 call
    client.post(
        "/tools/tool-calculator-001/use",
        json={"access_token": token, "inputs": {}},
    )

    # Second use should return 402
    resp = client.post(
        "/tools/tool-calculator-001/use",
        json={"access_token": token, "inputs": {}},
    )
    assert resp.status_code == 402


def test_use_tool_invalid_token(client):
    resp = client.post(
        "/tools/tool-web-search-001/use",
        json={"access_token": "invalid-token-xyz", "inputs": {}},
    )
    assert resp.status_code == 404
