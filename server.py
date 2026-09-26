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
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi import Request
from laya.serve import build_router, create_app
from laya.mcp.tools import ToolError, laya_predict, laya_preset, laya_route, laya_status
from mcp.server.transport_security import TransportSecuritySettings

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # MCP 2.x

    mcp_v2 = True
except ModuleNotFoundError:
    from mcp.server.fastmcp import FastMCP  # MCP 1.x

    mcp_v2 = False

if mcp_v2:
    from mcp.server.mcpserver.exceptions import ToolError as McpToolError
else:
    from mcp.server.fastmcp.exceptions import ToolError as McpToolError

# Keep model loads lazy unless the operator explicitly asks for startup preload.
os.environ.setdefault("LAYA_PRELOAD", "0")
os.environ.setdefault("LAYA_MAX_LOADED", "1")
os.environ.setdefault("LAYA_DEFAULT_MODEL", "multilingual")
# os.environ.setdefault("LAYA_API_KEY", "test")
router = build_router()
app = create_app(router=router)

# Use Laya's own request validation, inference worker, and optional API key.
systemone = next(route.endpoint for route in app.routes if route.path == "/v1/systemone")


def _replay(body):
    async def receive():
        return {"type": "http.request", "body": body}

    return receive


async def decisions(request: Request) -> Response:
    """Alias for /v1/systemone that accepts the friendly question aliases.

    Runs normalize_questions (prompt/question/text, choices/options, choice
    criteria list expansion) before delegating to Laya's native endpoint, so
    HTTP clients get the same leniency as the MCP tools instead of
    "a choice question takes 'criteria' as a dict of label -> description".
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and "questions" in payload:
        try:
            payload["questions"] = normalize_questions(payload["questions"])
        except ToolError as exc:
            return JSONResponse({"detail": exc.message}, status_code=400)
    replayed = Request(request.scope, _replay(json.dumps(payload).encode()))
    return await systemone(replayed, request.headers.get("authorization"))


app.add_api_route("/v1/decisions", decisions, methods=["POST"], include_in_schema=False)
app.add_api_route("/decisions", decisions, methods=["POST"], include_in_schema=False)


# @app.get("/tetris", include_in_schema=False)
# def tetris() -> FileResponse:
#     return FileResponse(Path(__file__).with_name("tetris.html"))


mcp_security = TransportSecuritySettings(
    allowed_hosts=["127.0.0.1:8000", "localhost:8000", "192.168.0.124:8000"],
)
mcp = FastMCP("laya") if mcp_v2 else FastMCP("laya", transport_security=mcp_security)


def normalize_questions(questions):
    """Map friendly question aliases onto Laya's schema.

    Laya's MCP validator requires every question to carry a non-empty
    ``instructions`` string (and ``criteria`` for choice/score types), a
    *choice* ``criteria`` object of label -> description, and a *score*
    ``criteria`` list of rubric levels. Callers often send ``prompt`` and
    ``choices``/``options`` instead, or a choice ``criteria`` list, which made
    laya_predict and laya_route fail with redacted "Error executing tool"
    messages. Accept both spellings, expand a choice criteria list
    ["a", "b"] to {"a": "a", "b": "b"} (the same expansion
    ``Agent._to_internal`` performs downstream), and fail early with a
    per-question message that survives the trip to the client.
    """
    if not isinstance(questions, dict) or not questions:
        raise ToolError("invalid_questions", "questions must be a non-empty object")
    normalized = {}
    for name, question in questions.items():
        if not isinstance(question, dict):
            raise ToolError("invalid_questions", f"questions[{name}] must be an object")
        question = dict(question)
        if not isinstance(question.get("instructions"), str) or not question["instructions"].strip():
            alias = None
            for key in ("prompt", "question", "text"):
                value = question.pop(key, None)
                if isinstance(value, str) and value.strip():
                    alias = value
                    break
                question.pop(key, None)
            if alias is None:
                raise ToolError(
                    "invalid_questions",
                    f"questions[{name}].instructions must be a non-empty string",
                )
            question["instructions"] = alias.strip()
        if not question.get("criteria"):
            for key in ("choices", "options"):
                value = question.pop(key, None)
                if value:
                    question["criteria"] = value
                    break
                question.pop(key, None)
        if not question.get("type"):
            question["type"] = "choice" if question.get("criteria") else "noul"
        if question["type"] in ("choice", "score") and not question.get("criteria"):
            raise ToolError(
                "invalid_questions",
                f"questions[{name}].criteria is required for type '{question['type']}'",
            )
        if question["type"] == "choice" and isinstance(question["criteria"], list):
            labels = question["criteria"]
            if not labels or not all(isinstance(c, str) and c.strip() for c in labels):
                raise ToolError(
                    "invalid_questions",
                    f"questions[{name}].criteria as a list must contain non-empty strings",
                )
            question["criteria"] = {label: label for label in labels}
        normalized[name] = question
    return normalized


# Laya's Rust-backed tokenizer mutates truncation config on every call
# (transformers tokenization_utils_fast.py set_truncation_and_padding), which is
# not thread-safe: two concurrent predict calls panic with
# "RuntimeError: Already borrowed". Sync MCP tools run in a threadpool, so a
# plain lock serializes inference. Calls take ~0.2-1s, so the cost is negligible.
_infer_lock = threading.Lock()


def mcp_result(fn, *args, **kwargs):
    """Run fn; raise McpToolError so isError=true AND the message reaches the client.

    mcp 2.x wraps any other exception as UnexpectedToolError("Error executing
    tool <name>") and redacts the original message. Only the SDK's own
    ToolError keeps our JSON payload on the wire, so schema mistakes come back
    to the LLM as a readable hint it can retry against, instead of a bare
    "Error executing tool laya_predict".
    """
    try:
        with _infer_lock:
            return fn(*args, **kwargs)
    except ToolError as exc:
        raise McpToolError(json.dumps({"error": exc.code, "message": exc.message})) from None
    except Exception as exc:
        logging.exception("MCP tool failed")
        raise McpToolError(
            json.dumps({"error": "internal_error", "message": f"{type(exc).__name__}: {exc}"})
        ) from None


@mcp.tool(name="laya_status")
def mcp_status() -> dict:
    """Report loaded checkpoints and device information."""
    return mcp_result(
        laya_status,
        router=router,
        preload=os.environ["LAYA_PRELOAD"].lower() in ("1", "true", "yes", "on"),
    )


@mcp.tool(name="laya_route")
def mcp_route(state: dict, questions: dict) -> dict:
    """Preview which checkpoint will handle typed questions.

    Each question: {"type": "noul"|"choice"|"score", "instructions": str,
    "criteria": {"label": "description"} for choice, [str, ...] for score}.
    "prompt"/"question"/"text" and "choices"/"options" are accepted as
    aliases for "instructions"/"criteria"; a choice criteria list
    ["a", "b"] is expanded to {"a": "a", "b": "b"}.
    """
    return mcp_result(lambda: laya_route(state, normalize_questions(questions), router=router))


@mcp.tool(name="laya_predict")
def mcp_predict(state: dict, questions: dict, model: str = "auto") -> dict:
    """Answer typed choice, score, or noul questions with Laya.

    Each question: {"type": "noul"|"choice"|"score", "instructions": str,
    "criteria": {"label": "description"} for choice, [str, ...] for score}.
    "prompt"/"question"/"text" and "choices"/"options" are accepted as
    aliases for "instructions"/"criteria"; a choice criteria list
    ["a", "b"] is expanded to {"a": "a", "b": "b"}.
    """
    return mcp_result(lambda: laya_predict(state, normalize_questions(questions), model, router=router))


@mcp.tool(name="laya_preset")
def mcp_preset(preset: str, state: dict) -> dict:
    """Run a guard, moderation, triage, or model_router preset."""
    import laya

    return mcp_result(
        laya_preset,
        preset,
        state,
        router=router,
        preset_builder=lambda name: getattr(laya, name)(),
    )


# A mounted app does not inherit the parent's lifespan or /v1/systemone auth.
mcp_app = mcp.streamable_http_app(transport_security=mcp_security) if mcp_v2 else mcp.streamable_http_app()
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
    uvicorn.run(
        app,
        host=os.environ.get("LAYA_HOST", "0.0.0.0"),
        port=int(os.environ.get("LAYA_PORT", "8000")),
    )
