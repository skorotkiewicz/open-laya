"""Probe the running MCP server: python -B test_mcp_http.py."""

import json
import os

import requests

base = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
headers = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
if os.environ.get("LAYA_API_KEY"):
    headers["Authorization"] = "Bearer " + os.environ["LAYA_API_KEY"]


def call(method, params, request_id):
    try:
        response = requests.post(
            base + "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"MCP request to {base}/mcp failed: {exc}") from exc
    data = next(
        (line[6:] for line in response.text.splitlines() if line.startswith("data: ")),
        response.text,
    )
    message = json.loads(data)
    if "error" in message:
        raise SystemExit(f"MCP {method} error: {message['error']}")
    if response.headers.get("mcp-session-id"):
        headers["mcp-session-id"] = response.headers["mcp-session-id"]
    return message["result"]


info = call(
    "initialize",
    {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "laya-smoke", "version": "1"},
    },
    1,
)
if info["serverInfo"]["name"] != "laya":
    raise SystemExit(f"Unexpected MCP server: {info['serverInfo']}")
tools = call("tools/list", {}, 2)["tools"]
if "laya_predict" not in {tool["name"] for tool in tools}:
    raise SystemExit("laya_predict is missing from MCP tools")
status = call("tools/call", {"name": "laya_status", "arguments": {}}, 3)
if status.get("isError"):
    raise SystemExit(f"laya_status failed: {status}")
print(f"Live MCP at {base}/mcp: handshake, tools and laya_status OK")
