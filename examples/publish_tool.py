"""Example: publish a new tool to the marketplace.

Usage:
    MAINLAYER_TOKEN=tok_... VENDOR_ID=vendor-123 python examples/publish_tool.py
"""

import os

import httpx

BASE_URL = os.environ.get("MARKETPLACE_URL", "http://localhost:8000")
TOKEN = os.environ.get("MAINLAYER_TOKEN", "demo-token")
VENDOR_ID = os.environ.get("VENDOR_ID", "vendor-demo-001")

HEADERS = {
    "x-mainlayer-token": TOKEN,
    "x-vendor-id": VENDOR_ID,
}

TOOL = {
    "name": "Sentiment Analyser",
    "description": (
        "Analyse the sentiment of any text and return a score from -1.0 (very negative) "
        "to +1.0 (very positive). Supports 20 languages. Ideal for customer feedback "
        "processing, social media monitoring, and product review analysis."
    ),
    "price_usdc": 0.001,
    "category": "ai",
    "tags": ["sentiment", "nlp", "ai", "text-analysis"],
    "mcp_endpoint": "https://tools.example.com/mcp/sentiment",
    "tool_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to analyse",
                "maxLength": 10000,
            },
            "language": {
                "type": "string",
                "description": "ISO 639-1 language code (auto-detect if omitted)",
                "default": "auto",
            },
        },
        "required": ["text"],
    },
}


def main() -> None:
    print(f"Publishing tool: {TOOL['name']!r}")

    resp = httpx.post(
        f"{BASE_URL}/tools",
        json=TOOL,
        headers=HEADERS,
        timeout=15,
    )

    if resp.status_code == 402:
        print("Payment required. Provide a valid MAINLAYER_TOKEN.")
        return

    resp.raise_for_status()
    data = resp.json()

    print(f"\nTool published successfully!")
    print(f"  ID       : {data['id']}")
    print(f"  Name     : {data['name']}")
    print(f"  Price    : ${data['price_usdc']:.4f} USDC/call")
    print(f"  Category : {data['category']}")
    print(f"  Resource : {data.get('mainlayer_resource_id', 'n/a')}")
    print(f"\nAgents can now install it via:")
    print(f"  POST {BASE_URL}/tools/{data['id']}/install")


if __name__ == "__main__":
    main()
