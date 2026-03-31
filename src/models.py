"""
Pydantic models for the MCP Tool Marketplace.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ToolCategory(str, Enum):
    SEARCH = "search"
    DATA = "data"
    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    ANALYTICS = "analytics"
    MEDIA = "media"
    UTILITIES = "utilities"
    AI = "ai"
    FINANCE = "finance"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Request / Response bodies
# ---------------------------------------------------------------------------


class PublishToolRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Human-readable tool name")
    description: str = Field(..., min_length=10, max_length=2000)
    price_usdc: float = Field(..., ge=0.001, le=1000.0, description="Price per call in USDC")
    tool_schema: Dict[str, Any] = Field(..., description="JSON Schema describing tool inputs/outputs")
    mcp_endpoint: str = Field(..., description="HTTPS endpoint that implements the MCP tool")
    category: ToolCategory = Field(ToolCategory.OTHER)
    tags: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("mcp_endpoint")
    @classmethod
    def endpoint_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("mcp_endpoint must use HTTPS")
        return v

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: List[str]) -> List[str]:
        return [t.lower().strip() for t in v if t.strip()][:10]


class ToolResponse(BaseModel):
    id: str
    name: str
    description: str
    price_usdc: float
    category: ToolCategory
    tags: List[str]
    mcp_endpoint: str
    tool_schema: Dict[str, Any]
    vendor_id: str
    mainlayer_resource_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    call_count: int = 0
    active: bool = True


class ToolListResponse(BaseModel):
    tools: List[ToolResponse]
    total: int
    page: int
    page_size: int


class PurchaseRequest(BaseModel):
    agent_api_key: str = Field(..., description="Mainlayer API key of the purchasing agent")
    quantity: int = Field(1, ge=1, le=1000, description="Number of calls to pre-purchase")


class PurchaseResponse(BaseModel):
    payment_id: str
    tool_id: str
    tool_name: str
    quantity: int
    amount_usdc: float
    status: str
    access_token: str
    calls_remaining: int
    expires_at: Optional[datetime] = None


class UseToolRequest(BaseModel):
    access_token: str = Field(..., description="Token returned by /purchase")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific input parameters")


class UseToolResponse(BaseModel):
    success: bool
    tool_id: str
    tool_name: str
    result: Any
    calls_remaining: int
    latency_ms: float


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class CategoryInfo(BaseModel):
    category: ToolCategory
    label: str
    description: str
    tool_count: int


# ---------------------------------------------------------------------------
# Internal / DB shapes
# ---------------------------------------------------------------------------


class ToolRecord(BaseModel):
    """Internal representation stored in the in-memory DB."""

    id: str
    name: str
    description: str
    price_usdc: float
    category: ToolCategory
    tags: List[str]
    mcp_endpoint: str
    tool_schema: Dict[str, Any]
    vendor_id: str
    mainlayer_resource_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    call_count: int = 0
    active: bool = True

    def to_response(self) -> ToolResponse:
        return ToolResponse(**self.model_dump())


class AccessRecord(BaseModel):
    """Tracks pre-purchased call credits."""

    access_token: str
    tool_id: str
    agent_api_key: str
    calls_remaining: int
    calls_total: int
    payment_id: str
    created_at: datetime
    expires_at: Optional[datetime]
