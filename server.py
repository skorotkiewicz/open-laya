#!/usr/bin/env python3
r"""Run Laya's HTTP server with decision aliases and MCP tools.

Choose a checkpoint for one request:
    curl -H 'Content-Type: application/json' \
      -d '{"model":"typed-decisions","state":"Please refund me","questions":{"refund":{"type":"noul","instructions":"Is a refund requested?"}}}' \
      http://localhost:8000/v1/decisions

Use english, multilingual, or typed-decisions. Omit model for language routing;
the response's routing.model shows the checkpoint Laya selected.
"""

import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse, Response
from laya.serve import build_router, create_app
from laya.mcp.tools import ToolError, laya_predict, laya_preset, laya_route, laya_status

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # MCP 2.x
except ModuleNotFoundError:
    from mcp.server.fastmcp import FastMCP  # MCP 1.x

# Keep model loads lazy unless the operator explicitly asks for startup preload.
os.environ.setdefault("LAYA_PRELOAD", "0")
router = build_router()
app = create_app(router=router)

# Use Laya's own request validation, inference worker, and optional API key.
systemone = next(route.endpoint for route in app.routes if route.path == "/v1/systemone")
app.add_api_route("/v1/decisions", systemone, methods=["POST"], include_in_schema=False)
app.add_api_route("/decisions", systemone, methods=["POST"], include_in_schema=False)


# @app.get("/tetris", include_in_schema=False)
# def tetris() -> FileResponse:
#     return FileResponse(Path(__file__).with_name("tetris.html"))


mcp = FastMCP("laya")


def mcp_result(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ToolError as exc:
        raise ValueError(exc.message) from None
    except Exception:
        logging.exception("MCP tool failed")
        raise ValueError("MCP tool failed") from None


@mcp.tool(name="laya_status")
def mcp_status() -> dict:
    """Report loaded checkpoints and device information."""
    return mcp_result(laya_status, router=router,
                      preload=os.environ["LAYA_PRELOAD"].lower() in ("1", "true", "yes", "on"))


@mcp.tool(name="laya_route")
def mcp_route(state: dict, questions: dict) -> dict:
    """Preview which checkpoint will handle typed questions."""
    return mcp_result(laya_route, state, questions, router=router)


@mcp.tool(name="laya_predict")
def mcp_predict(state: dict, questions: dict, model: str = "auto") -> dict:
    """Answer typed choice, score, or noul questions with Laya."""
    return mcp_result(laya_predict, state, questions, model, router=router)


@mcp.tool(name="laya_preset")
def mcp_preset(preset: str, state: dict) -> dict:
    """Run a guard, moderation, triage, or model_router preset."""
    import laya

    return mcp_result(laya_preset, preset, state, router=router,
                      preset_builder=lambda name: getattr(laya, name)())


# A mounted app does not inherit the parent's lifespan or /v1/systemone auth.
mcp_app = mcp.streamable_http_app()
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(host):
    async with original_lifespan(host), mcp.session_manager.run():
        yield


app.router.lifespan_context = lifespan
expected_auth = ("Bearer " + os.environ["LAYA_API_KEY"]).encode() if os.environ.get("LAYA_API_KEY") else None


async def protected_mcp(scope, receive, send):
    if scope["type"] == "http" and expected_auth is not None:
        supplied = dict(scope["headers"]).get(b"authorization", b"")
        if not hmac.compare_digest(supplied, expected_auth):
            await Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
            return
    await mcp_app(scope, receive, send)


# The MCP SDK serves /mcp within its app. Mount last so normal routes win.
app.mount("/", protected_mcp)


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("LAYA_HOST", "0.0.0.0"),
                port=int(os.environ.get("LAYA_PORT", "8000")))
