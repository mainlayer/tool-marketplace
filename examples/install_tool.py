"""Example: install a marketplace tool and invoke it.

Usage:
    AGENT_API_KEY=ak_... python examples/install_tool.py
"""

import os

import httpx

BASE_URL = os.environ.get("MARKETPLACE_URL", "http://localhost:8000")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "ak_demo_agent_001")

# Use the built-in Web Search sample tool
TOOL_ID = os.environ.get("TOOL_ID", "tool-web-search-001")


def list_tools() -> None:
    resp = httpx.get(f"{BASE_URL}/tools", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    print(f"Available tools ({data['total']} total):")
    for tool in data["tools"][:5]:
        print(f"  [{tool['id']}] {tool['name']}  ${tool['price_usdc']:.4f}/call — {tool['category']}")


def install_tool(tool_id: str, quantity: int = 5) -> str:
    resp = httpx.post(
        f"{BASE_URL}/tools/{tool_id}/install",
        json={"agent_api_key": AGENT_API_KEY, "quantity": quantity},
        timeout=15,
    )

    if resp.status_code == 402:
        print(f"Payment failed: {resp.json()}")
        return ""

    resp.raise_for_status()
    data = resp.json()

    print(f"\nTool installed: {data['tool_name']}")
    print(f"  Payment ID   : {data['payment_id']}")
    print(f"  Calls bought : {data['quantity']}")
    print(f"  Cost         : {data['amount_usdc']:.4f} USDC")
    print(f"  Access token : {data['access_token'][:16]}...")
    print(f"  Calls left   : {data['calls_remaining']}")
    return data["access_token"]


def use_tool(tool_id: str, access_token: str) -> None:
    resp = httpx.post(
        f"{BASE_URL}/tools/{tool_id}/use",
        json={
            "access_token": access_token,
            "inputs": {"query": "latest AI research papers 2025", "num_results": 3},
        },
        timeout=15,
    )

    if resp.status_code == 402:
        print("No calls remaining. Purchase more via /install.")
        return

    resp.raise_for_status()
    data = resp.json()

    print(f"\nTool invoked: {data['tool_name']}")
    print(f"  Latency      : {data['latency_ms']} ms")
    print(f"  Calls left   : {data['calls_remaining']}")
    print(f"  Result       : {data['result']}")


def main() -> None:
    list_tools()
    token = install_tool(TOOL_ID, quantity=3)
    if token:
        use_tool(TOOL_ID, token)


if __name__ == "__main__":
    main()
