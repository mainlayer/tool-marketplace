# MCP Tool Marketplace — Mainlayer

Browse, publish, and install MCP-compatible tools. Per-install billing handled by [Mainlayer](https://mainlayer.fr).

Comes pre-loaded with 5 sample tools: Web Search, Calculator, Weather, Translator, Summariser.

## Endpoints

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| `GET` | `/tools` | free | List tools |
| `GET` | `/tools/{id}` | free | Tool details |
| `POST` | `/tools` | Mainlayer | Publish a tool |
| `POST` | `/tools/{id}/install` | per-install | Purchase calls |
| `POST` | `/tools/{id}/use` | — | Invoke tool (uses purchased calls) |
| `GET` | `/categories` | free | Category counts |

## Quick start

```bash
pip install -e ".[dev]"
MAINLAYER_API_KEY=sk_... uvicorn src.main:app --reload
```

## Install a tool (agent workflow)

```bash
# 1. Browse tools
curl http://localhost:8000/tools

# 2. Purchase 10 calls
curl -X POST http://localhost:8000/tools/tool-web-search-001/install \
  -H "Content-Type: application/json" \
  -d '{"agent_api_key": "ak_your_key", "quantity": 10}'

# 3. Use the tool with the returned access_token
curl -X POST http://localhost:8000/tools/tool-web-search-001/use \
  -H "Content-Type: application/json" \
  -d '{"access_token": "...", "inputs": {"query": "latest AI news"}}'
```

## Running tests

```bash
pytest tests/ -v
```
