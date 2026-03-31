# MCP Tool Marketplace

![CI](https://github.com/mainlayer/tool-marketplace/actions/workflows/ci.yml/badge.svg) ![License](https://img.shields.io/badge/license-MIT-blue)

MCP-compatible tool marketplace powered by Mainlayer. Publish, discover, and install tools with per-install billing for autonomous agents.

## Overview

This template demonstrates a production-ready tool marketplace where:

- **Tool Publishers** upload MCP-compatible tools with pricing
- **Agents** browse tools by category and tags, purchase call quotas
- **Mainlayer** handles per-install billing and quota management
- **Access Tokens** grant time-limited access to purchased tool calls

## Installation

```bash
pip install mainlayer fastapi uvicorn pydantic
```

## Quick Start

### 1. Set your Mainlayer API key

```bash
export MAINLAYER_API_KEY="sk_..."
uvicorn src.main:app --reload
```

### 2. Browse available tools

```bash
curl http://localhost:8000/tools
```

Response:

```json
{
  "tools": [
    {
      "id": "tool-web-search-001",
      "name": "Web Search",
      "description": "Search the web and return results",
      "category": "search",
      "tags": ["search", "web", "information"],
      "price_usdc": 0.10,
      "calls_total": 5234
    }
  ],
  "total": 5,
  "page": 1
}
```

### 3. Browse by category

```bash
curl http://localhost:8000/tools?category=search
```

### 4. Get tool details

```bash
curl http://localhost:8000/tools/tool-web-search-001
```

### 5. View categories with tool counts

```bash
curl http://localhost:8000/categories
```

Response:

```json
{
  "categories": [
    {
      "category": "search",
      "label": "Search & Discovery",
      "tool_count": 3
    },
    {
      "category": "utilities",
      "label": "Utilities",
      "tool_count": 2
    }
  ],
  "total_tools": 5
}
```

### 6. Publish a new tool (vendor workflow)

```bash
curl -X POST http://localhost:8000/tools \
  -H "Content-Type: application/json" \
  -H "x-mainlayer-token: sk_..." \
  -H "x-vendor-id: vendor-001" \
  -d '{
    "name": "Email Validator",
    "description": "Validate and verify email addresses",
    "category": "utilities",
    "tags": ["email", "validation", "verification"],
    "price_usdc": 0.05,
    "mcp_endpoint": "mcp://validator.example.com",
    "tool_schema": {
      "type": "object",
      "properties": {
        "email": {"type": "string"}
      },
      "required": ["email"]
    }
  }'
```

### 7. Purchase tool calls (agent workflow)

```bash
curl -X POST http://localhost:8000/tools/tool-web-search-001/install \
  -H "Content-Type: application/json" \
  -H "x-mainlayer-token: sk_agent_..." \
  -d '{
    "agent_api_key": "ak_your_agent_key",
    "quantity": 100
  }'
```

Response:

```json
{
  "payment_id": "pay_...",
  "tool_id": "tool-web-search-001",
  "tool_name": "Web Search",
  "quantity": 100,
  "amount_usdc": 10.00,
  "access_token": "at_...",
  "calls_remaining": 100,
  "expires_at": "2025-02-20T10:30:00Z"
}
```

### 8. Use the tool (agent invocation)

```bash
curl -X POST http://localhost:8000/tools/tool-web-search-001/use \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "at_...",
    "inputs": {
      "query": "latest AI breakthroughs 2025"
    }
  }'
```

Response:

```json
{
  "success": true,
  "tool_id": "tool-web-search-001",
  "tool_name": "Web Search",
  "result": {
    "status": "success",
    "output": "[Search results...]"
  },
  "calls_remaining": 99,
  "latency_ms": 245.3
}
```

## API Endpoints

### Tools (Free)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tools` | List tools (filterable, searchable, paginated) |
| `GET` | `/tools/{id}` | Get tool details |
| `GET` | `/categories` | List categories with counts |

### Publishing (Paid)

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| `POST` | `/tools` | Mainlayer | Publish a new tool |

### Installation (Paid)

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| `POST` | `/tools/{id}/install` | per-install | Purchase call quota |

### Usage

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| `POST` | `/tools/{id}/use` | free (prepaid) | Invoke tool with purchased quota |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

## Features

- **Tool Discovery**: Browse 5+ pre-loaded tools (search, calc, weather, translator, summarizer)
- **Category Filtering**: Organize tools by search, data, communication, productivity, etc.
- **Full-text Search**: Search by name and description
- **Per-Install Billing**: Charge agents per tool call quota purchased
- **Access Tokens**: Time-limited tokens (30 days default) for tool access
- **Call Tracking**: Decrement calls-remaining on each invocation
- **MCP Compatible**: Tools follow Model Context Protocol specification
- **Vendor Support**: Multiple vendors can publish tools
- **Error Handling**: 402 for insufficient funds, 404 for missing tools

## Architecture

```
Vendor (POST /tools with Mainlayer token)
        ↓
Register Tool as Mainlayer Resource
        ↓
Tool added to marketplace registry
        ↓
Agent (GET /tools)
        ↓
Browse and find tool
        ↓
Agent (POST /tools/{id}/install with payment token)
        ↓
Mainlayer charges per-install fee
        ↓
Generate access token + grant call quota
        ↓
Agent (POST /tools/{id}/use with access_token)
        ↓
Execute tool, decrement quota
        ↓
Agent runs out of quota → purchase more calls
```

## Tool Registry Schema

Tools are stored with:

```python
{
  "id": "tool-web-search-001",
  "name": "Web Search",
  "description": "Search the web",
  "vendor_id": "vendor-001",
  "category": "search",
  "tags": ["search", "web"],
  "price_usdc": 0.10,
  "mcp_endpoint": "mcp://...",
  "tool_schema": {...},
  "created_at": "2025-01-20T10:00:00Z",
  "calls_total": 5234,
  "mainlayer_resource_id": "res_..."
}
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Format
ruff format src/
```

## Production Deployment

1. Replace in-memory registry with PostgreSQL
2. Persist access tokens in Redis or database
3. Implement webhook handlers for payment notifications
4. Add tool result caching layer
5. Set up usage analytics and billing reports
6. Implement vendor dashboard with earnings tracking
7. Add content moderation and tool verification
8. Configure rate limiting and abuse detection
9. Set up monitoring and alerting (DataDog, New Relic)

## Monetization Strategies

- **Per-Install Fees**: Charge agents each time they purchase tool calls
- **Percentage Cut**: Take 30% of tool revenue, pay vendors 70%
- **Tiered Pricing**: Discounts for bulk purchases
- **Subscription Model**: Agents pay monthly for unlimited tool access
- **Free Tier**: Freemium tools to drive adoption

## Support

- Docs: [mainlayer.fr](https://mainlayer.fr)
- Issues: [GitHub Issues](https://github.com/mainlayer/tool-marketplace/issues)
