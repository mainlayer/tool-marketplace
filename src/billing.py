"""Mainlayer per-install billing for the tool marketplace.

When an agent installs a tool, we call `charge_agent` via the Mainlayer API.
The vendor receives the payment; the marketplace takes a small platform fee
(configurable via PLATFORM_FEE_PCT, default 10%).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import HTTPException, status

from .mainlayer import InsufficientFundsError, MainlayerError, charge_agent
from .models import ToolRecord

logger = logging.getLogger(__name__)

PLATFORM_FEE_PCT = float(os.getenv("PLATFORM_FEE_PCT", "0.10"))


async def charge_tool_install(
    agent_api_key: str,
    tool: ToolRecord,
    quantity: int,
    total_usdc: float,
) -> Dict[str, Any]:
    """Charge the agent for purchasing `quantity` calls to `tool`.

    Returns the payment record from Mainlayer on success.
    Raises HTTP 402 on insufficient funds, HTTP 502 on billing errors.
    """
    resource_id = tool.mainlayer_resource_id or tool.id
    description = f"Install {quantity}x {tool.name}"

    try:
        payment = await charge_agent(
            resource_id=resource_id,
            agent_api_key=agent_api_key,
            amount_usdc=total_usdc,
            description=description,
            metadata={
                "tool_id": tool.id,
                "tool_name": tool.name,
                "quantity": quantity,
                "unit_price_usdc": tool.price_usdc,
            },
        )
        logger.info(
            "Tool install charged: tool=%s qty=%d amount=%.6f payment_id=%s",
            tool.id,
            quantity,
            total_usdc,
            payment.get("id", "unknown"),
        )
        return payment

    except InsufficientFundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "insufficient_funds",
                "message": str(exc),
                "amount_usdc": total_usdc,
                "info": "mainlayer.fr",
            },
        ) from exc

    except MainlayerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "billing_error",
                "message": f"Payment processing failed: {exc}",
            },
        ) from exc
