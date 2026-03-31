"""
Mainlayer API integration layer.

Wraps the Mainlayer payment API (https://api.mainlayer.xyz) for:
  - Creating resources (tools listed on the marketplace)
  - Charging agents for tool access
  - Verifying payment status

All network calls use httpx with a shared async client for connection pooling.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

MAINLAYER_BASE_URL = os.getenv("MAINLAYER_BASE_URL", "https://api.mainlayer.xyz")
MAINLAYER_API_KEY = os.getenv("MAINLAYER_API_KEY", "")

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=MAINLAYER_BASE_URL,
            timeout=httpx.Timeout(30.0),
            headers={
                "Authorization": f"Bearer {MAINLAYER_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "tool-marketplace/1.0",
            },
        )
    return _client


async def close_client() -> None:
    """Close the shared httpx client on shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Resource management
# ---------------------------------------------------------------------------


async def create_resource(
    name: str,
    description: str,
    price_usdc: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Register a tool as a payable Mainlayer resource.

    Returns the full resource object from Mainlayer including the resource ID
    that should be stored alongside the tool record.
    """
    if not MAINLAYER_API_KEY:
        logger.warning("MAINLAYER_API_KEY not set — returning mock resource")
        return _mock_resource(name, price_usdc)

    payload: Dict[str, Any] = {
        "name": name,
        "description": description,
        "price": {
            "amount": price_usdc,
            "currency": "usdc",
        },
    }
    if metadata:
        payload["metadata"] = metadata

    try:
        client = _get_client()
        response = await client.post("/v1/resources", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Mainlayer create_resource failed: %s %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise MainlayerError(
            f"Failed to create Mainlayer resource: {exc.response.status_code}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Mainlayer network error: %s", exc)
        raise MainlayerError("Network error communicating with Mainlayer") from exc


async def charge_agent(
    resource_id: str,
    agent_api_key: str,
    amount_usdc: float,
    description: str = "Tool call payment",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Charge an agent's Mainlayer account for tool usage.

    Returns the payment record including a unique payment_id.
    """
    if not MAINLAYER_API_KEY:
        logger.warning("MAINLAYER_API_KEY not set — returning mock payment")
        return _mock_payment(resource_id, amount_usdc)

    payload: Dict[str, Any] = {
        "resource_id": resource_id,
        "amount": {
            "value": amount_usdc,
            "currency": "usdc",
        },
        "payer_api_key": agent_api_key,
        "description": description,
    }
    if metadata:
        payload["metadata"] = metadata

    try:
        client = _get_client()
        response = await client.post("/v1/payments", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Mainlayer charge_agent failed: %s %s",
            exc.response.status_code,
            exc.response.text,
        )
        if exc.response.status_code == 402:
            raise InsufficientFundsError(
                "Agent has insufficient funds for this purchase"
            ) from exc
        raise MainlayerError(
            f"Payment failed: {exc.response.status_code}",
            status_code=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Mainlayer network error: %s", exc)
        raise MainlayerError("Network error communicating with Mainlayer") from exc


async def get_payment(payment_id: str) -> Dict[str, Any]:
    """Retrieve a payment record by ID."""
    if not MAINLAYER_API_KEY:
        return {"id": payment_id, "status": "succeeded"}

    try:
        client = _get_client()
        response = await client.get(f"/v1/payments/{payment_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise MainlayerError(
            f"Failed to retrieve payment: {exc.response.status_code}",
            status_code=exc.response.status_code,
        ) from exc


async def verify_agent_balance(
    agent_api_key: str, required_amount: float
) -> bool:
    """
    Check that an agent has sufficient balance.

    Returns True if the agent can afford the charge, False otherwise.
    Falls back to True in mock mode so tests pass without credentials.
    """
    if not MAINLAYER_API_KEY:
        return True

    try:
        client = _get_client()
        # Use agent's own key to check their balance
        response = await client.get(
            "/v1/balance",
            headers={"Authorization": f"Bearer {agent_api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        balance = float(data.get("available", {}).get("usdc", 0))
        return balance >= required_amount
    except (httpx.HTTPStatusError, httpx.RequestError, KeyError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Mock helpers (used when MAINLAYER_API_KEY is not set)
# ---------------------------------------------------------------------------


def _mock_resource(name: str, price_usdc: float) -> Dict[str, Any]:
    import uuid

    return {
        "id": f"res_mock_{uuid.uuid4().hex[:12]}",
        "name": name,
        "price": {"amount": price_usdc, "currency": "usdc"},
        "status": "active",
        "mock": True,
    }


def _mock_payment(resource_id: str, amount_usdc: float) -> Dict[str, Any]:
    import uuid

    return {
        "id": f"pay_mock_{uuid.uuid4().hex[:12]}",
        "resource_id": resource_id,
        "amount": {"value": amount_usdc, "currency": "usdc"},
        "status": "succeeded",
        "mock": True,
    }


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class MainlayerError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class InsufficientFundsError(MainlayerError):
    def __init__(self, message: str = "Insufficient funds") -> None:
        super().__init__(message, status_code=402)
