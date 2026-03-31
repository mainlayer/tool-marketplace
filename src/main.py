"""MCP Tool Marketplace — FastAPI application.

Endpoints
---------
GET  /tools                    — list available tools (free)
POST /tools                    — publish a new tool
GET  /tools/{id}               — get tool details (free)
POST /tools/{id}/install       — purchase calls to a tool (Mainlayer billing)
POST /tools/{id}/use           — use a pre-purchased tool call
GET  /categories               — list tool categories with counts (free)
GET  /health                   — health probe (free)
"""

from __future__ import annotations

import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .billing import charge_tool_install
from .models import (
    AccessRecord,
    CategoryInfo,
    ErrorResponse,
    PublishToolRequest,
    PurchaseRequest,
    PurchaseResponse,
    ToolCategory,
    ToolListResponse,
    ToolResponse,
    UseToolRequest,
    UseToolResponse,
)
from .registry import get_db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("tool-marketplace")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MCP Tool Marketplace",
    description=(
        "Browse, publish, and install MCP-compatible tools. "
        "Per-install billing powered by Mainlayer."
    ),
    version="1.0.0",
    contact={"name": "Mainlayer", "url": "https://mainlayer.fr"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes — free
# ---------------------------------------------------------------------------


@app.get(
    "/tools",
    response_model=ToolListResponse,
    tags=["Tools"],
    summary="List available tools",
)
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Full-text search"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ToolListResponse:
    """Return a paginated list of published tools."""
    db = get_db()
    tools, total = db.list_tools(
        category=category,
        tag=tag,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ToolListResponse(
        tools=[t.to_response() for t in tools],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get(
    "/tools/{tool_id}",
    response_model=ToolResponse,
    tags=["Tools"],
    summary="Get tool details",
    responses={404: {"model": ErrorResponse, "description": "Tool not found"}},
)
async def get_tool(tool_id: str) -> ToolResponse:
    """Return full details for a single tool."""
    db = get_db()
    tool = db.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"Tool '{tool_id}' not found."})
    return tool.to_response()


@app.get(
    "/categories",
    tags=["Tools"],
    summary="List categories with tool counts",
)
async def list_categories() -> dict:
    """Return all tool categories and their current tool counts."""
    db = get_db()
    counts = db.category_counts()
    categories = []
    labels = {
        ToolCategory.SEARCH: "Search & Discovery",
        ToolCategory.DATA: "Data & Analytics",
        ToolCategory.COMMUNICATION: "Communication",
        ToolCategory.PRODUCTIVITY: "Productivity",
        ToolCategory.ANALYTICS: "Analytics",
        ToolCategory.MEDIA: "Media & Files",
        ToolCategory.UTILITIES: "Utilities",
        ToolCategory.AI: "AI & ML",
        ToolCategory.FINANCE: "Finance",
        ToolCategory.OTHER: "Other",
    }
    for cat in ToolCategory:
        count = counts.get(cat.value, 0)
        if count > 0:
            categories.append(
                CategoryInfo(
                    category=cat,
                    label=labels.get(cat, cat.value.title()),
                    description=f"Tools in the {cat.value} category.",
                    tool_count=count,
                ).model_dump()
            )
    return {"categories": categories, "total_tools": sum(counts.values())}


# ---------------------------------------------------------------------------
# Routes — paid
# ---------------------------------------------------------------------------


@app.post(
    "/tools",
    response_model=ToolResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tools"],
    summary="Publish a new tool",
    responses={402: {"model": ErrorResponse, "description": "Payment required"}},
)
async def publish_tool(
    body: PublishToolRequest,
    x_mainlayer_token: str = Header(default="", alias="x-mainlayer-token"),
    x_vendor_id: str = Header(default="", alias="x-vendor-id"),
) -> ToolResponse:
    """Publish an MCP tool to the marketplace.

    The tool is registered as a Mainlayer resource so agents can pay for it.
    Supply `x-mainlayer-token` and `x-vendor-id`.
    """
    if not x_mainlayer_token:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "payment_required", "info": "mainlayer.fr"},
        )

    vendor_id = x_vendor_id or f"vendor-{str(uuid.uuid4())[:8]}"

    # Register tool with Mainlayer to get a resource ID
    from .mainlayer import create_resource, MainlayerError, InsufficientFundsError
    try:
        resource = await create_resource(
            name=body.name,
            description=body.description,
            price_usdc=body.price_usdc,
            metadata={"vendor_id": vendor_id, "category": body.category.value},
        )
    except (MainlayerError, InsufficientFundsError) as exc:
        raise HTTPException(status_code=502, detail={"error": "billing_error", "detail": str(exc)})

    db = get_db()
    record = db.create_tool(
        {
            "name": body.name,
            "description": body.description,
            "price_usdc": body.price_usdc,
            "category": body.category,
            "tags": body.tags,
            "mcp_endpoint": body.mcp_endpoint,
            "tool_schema": body.tool_schema,
            "vendor_id": vendor_id,
            "mainlayer_resource_id": resource.get("id"),
        }
    )

    logger.info("Tool published: id=%s name=%s vendor=%s", record.id, record.name, vendor_id)
    return record.to_response()


@app.post(
    "/tools/{tool_id}/install",
    response_model=PurchaseResponse,
    tags=["Tools"],
    summary="Purchase calls to a tool (Mainlayer billing)",
    responses={
        402: {"model": ErrorResponse, "description": "Insufficient funds"},
        404: {"model": ErrorResponse, "description": "Tool not found"},
    },
)
async def install_tool(
    tool_id: str,
    body: PurchaseRequest,
    x_mainlayer_token: str = Header(default="", alias="x-mainlayer-token"),
) -> PurchaseResponse:
    """Purchase a set of calls to a tool.

    Returns an `access_token` that can be used to invoke the tool via
    `POST /tools/{id}/use`. Each call consumes one unit of the purchased
    quantity.

    Billing is processed via Mainlayer using the agent's API key.
    """
    db = get_db()
    tool = db.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    total_usdc = round(tool.price_usdc * body.quantity, 6)
    payment = await charge_tool_install(
        agent_api_key=body.agent_api_key,
        tool=tool,
        quantity=body.quantity,
        total_usdc=total_usdc,
    )

    access_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)

    db.create_access(
        {
            "access_token": access_token,
            "tool_id": tool_id,
            "agent_api_key": body.agent_api_key[:8] + "...",
            "calls_remaining": body.quantity,
            "calls_total": body.quantity,
            "payment_id": payment.get("id", "mock"),
            "created_at": datetime.now(tz=timezone.utc),
            "expires_at": expires_at,
        }
    )

    logger.info("Tool installed: tool=%s qty=%d amount=%.4f", tool_id, body.quantity, total_usdc)
    return PurchaseResponse(
        payment_id=payment.get("id", "mock"),
        tool_id=tool_id,
        tool_name=tool.name,
        quantity=body.quantity,
        amount_usdc=total_usdc,
        status=payment.get("status", "succeeded"),
        access_token=access_token,
        calls_remaining=body.quantity,
        expires_at=expires_at,
    )


@app.post(
    "/tools/{tool_id}/use",
    response_model=UseToolResponse,
    tags=["Tools"],
    summary="Invoke a purchased tool",
    responses={
        402: {"model": ErrorResponse, "description": "No calls remaining"},
        404: {"model": ErrorResponse, "description": "Tool or access token not found"},
    },
)
async def use_tool(
    tool_id: str,
    body: UseToolRequest,
) -> UseToolResponse:
    """Invoke a tool using a pre-purchased access token.

    Each call consumes one unit. When `calls_remaining` reaches zero,
    the token is exhausted and a new purchase is required.
    """
    db = get_db()
    tool = db.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": "Tool not found."})

    access = db.get_access(body.access_token)
    if not access or access.tool_id != tool_id:
        raise HTTPException(status_code=404, detail={"error": "invalid_token", "detail": "Access token not found."})

    if access.calls_remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail={"error": "no_calls_remaining", "detail": "Purchase more calls via POST /tools/{id}/install."},
        )

    # Check expiry
    if access.expires_at and access.expires_at < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=402, detail={"error": "token_expired"})

    start = time.perf_counter()
    result = _mock_tool_call(tool.name, body.inputs)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    updated = db.decrement_access(body.access_token)
    db.increment_call_count(tool_id)

    return UseToolResponse(
        success=True,
        tool_id=tool_id,
        tool_name=tool.name,
        result=result,
        calls_remaining=updated.calls_remaining if updated else 0,
        latency_ms=latency_ms,
    )


def _mock_tool_call(tool_name: str, inputs: dict) -> dict:
    """Simulate a tool response. Replace with real MCP forwarding in production."""
    return {
        "tool": tool_name,
        "status": "success",
        "output": f"Mock result for {tool_name} with inputs: {inputs}",
        "mock": True,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Info"], include_in_schema=False)
async def health() -> dict:
    return {"status": "ok", "service": "tool-marketplace"}


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": str(exc)},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
