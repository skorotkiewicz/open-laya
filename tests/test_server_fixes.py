"""Regression tests for server.py MCP schema handling (no server or GPU needed).

Run:  python3 test_server_fixes.py

Covers the three failures seen in fix2.log:
1. choice questions with array criteria were rejected by the core validator
    ("criteria must be a non-empty object of label -> description").
2. score questions without criteria raised a bare ValueError whose message
    was redacted by MCP 2.x ("Error executing tool laya_predict").
3. normalize_questions ran OUTSIDE mcp_result, so its errors were redacted too.
"""

import json
import sys
import types


class ToolError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


# Mirrors the SDK's exceptions.ToolError, which takes a single message string.
class McpToolError(Exception):
    pass


def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class FakeApp:
    def __init__(self):
        self.routes = [types.SimpleNamespace(path="/v1/systemone", endpoint=lambda: None)]
        self.router = types.SimpleNamespace(lifespan_context=lambda *a: None)

    def add_api_route(self, *a, **k):
        pass

    def mount(self, *a, **k):
        pass


class FakeRequest:
    """Just enough of starlette's Request for the decisions() wrapper."""

    def __init__(self, scope, receive):
        self.scope, self._receive = scope, receive

    @property
    def headers(self):
        return {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in self.scope.get("headers", [])
        }

    async def body(self):
        return (await self._receive())["body"]

    async def receive(self):
        return await self._receive()


laya_pkg = _mod("laya", __path__=[])
serve = _mod("laya.serve", build_router=lambda: None, create_app=lambda router=None: FakeApp())
mcp_tools = _mod(
    "laya.mcp.tools",
    ToolError=ToolError,
    laya_predict=lambda state, questions, model="auto", router=None: {"answers": questions},
    laya_route=lambda *a, **k: {},
    laya_status=lambda *a, **k: {},
    laya_preset=lambda *a, **k: {},
)
_mod("laya.mcp", tools=mcp_tools)
laya_pkg.serve = serve
laya_pkg.mcp = sys.modules["laya.mcp"]


class MCPServer:
    def __init__(self, *a, **k):
        pass

    def tool(self, *a, **k):
        def deco(fn):
            return fn

        return deco

    def streamable_http_app(self, *a, **k):
        return FakeApp()


_mod("mcp")
_mod("mcp.server")
_mod("mcp.server.mcpserver", MCPServer=MCPServer)
_mod("mcp.server.mcpserver.exceptions", ToolError=McpToolError)
_mod(
    "mcp.server.transport_security",
    TransportSecuritySettings=lambda **k: types.SimpleNamespace(**k),
)
_mod("uvicorn", run=lambda *a, **k: None)
_mod("fastapi", Request=FakeRequest)
_mod(
    "fastapi.responses",
    FileResponse=object,
    Response=object,
    JSONResponse=lambda data, status_code=500: (data, status_code),
)

import importlib.util

spec = importlib.util.spec_from_file_location("srv", "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

# 1. choice with array criteria (the exact shape that crashed in fix2.log)
out = srv.normalize_questions(
    {
        "q1": {
            "type": "choice",
            "prompt": "Which backend?",
            "choices": ["CPU", "CUDA", "TPU"],
        }
    }
)
assert out["q1"]["criteria"] == {"CPU": "CPU", "CUDA": "CUDA", "TPU": "TPU"}, out
assert out["q1"]["instructions"] == "Which backend?"
print("1. choice array -> object expansion OK:", out["q1"]["criteria"])

# 2. score without criteria -> readable ToolError (was a redacted ValueError)
try:
    srv.normalize_questions({"score_q": {"prompt": "How rude 0-3?", "type": "score"}})
    raise SystemExit("should have raised")
except srv.ToolError as e:
    print("2. score missing criteria -> readable error:", e.message)

# 3. score with array criteria still passes through
out = srv.normalize_questions(
    {
        "q1": {
            "type": "score",
            "prompt": "How rude 0-3?",
            "criteria": ["0", "1", "2", "3"],
        }
    }
)
assert out["q1"]["criteria"] == ["0", "1", "2", "3"]
print("3. score array passthrough OK")

# 4. choice object criteria via aliases
out = srv.normalize_questions(
    {
        "backend": {
            "type": "choice",
            "prompt": "Which?",
            "choices": {"CPU": "processor", "CUDA": "gpu"},
        }
    }
)
assert out["backend"]["criteria"] == {"CPU": "processor", "CUDA": "gpu"}
print("4. choice object via aliases OK")

# 5. mcp_result surfaces the message instead of redacting
try:
    srv.mcp_result(
        lambda: (_ for _ in ()).throw(ToolError("invalid_questions", "criteria must be an object"))
    )
    raise SystemExit("should have raised")
except srv.McpToolError as e:
    payload = json.loads(str(e))
    assert payload == {
        "error": "invalid_questions",
        "message": "criteria must be an object",
    }, payload
    print("5. mcp_result surfaces message OK:", payload)

# 6. tool-level: normalize errors now raised INSIDE mcp_result (bare ValueErrors before)
try:
    srv.mcp_predict(state={"text": "hi"}, questions={"q1": {"type": "score", "prompt": "rate"}})
    raise SystemExit("should have raised")
except srv.McpToolError as e:
    payload = json.loads(str(e))
    assert payload["error"] == "invalid_questions" and "criteria" in payload["message"]
    print("6. predict schema error surfaced OK:", payload)

# 7. happy path end-to-end through mcp_predict
out = srv.mcp_predict(
    state={"text": "hi"},
    questions={"q1": {"type": "choice", "prompt": "p", "choices": ["a", "b"]}},
)
assert out["answers"]["q1"]["criteria"] == {"a": "a", "b": "b"}
print("7. mcp_predict end-to-end OK")

# 8. mcp_result serializes concurrent calls (the "Already borrowed" tokenizer race)
import threading
import time

active, max_active = 0, 0
results = []


def slow_fn():
    global active, max_active
    active += 1
    max_active = max(max_active, active)
    time.sleep(0.05)
    active -= 1
    return "ok"


threads = [threading.Thread(target=lambda: results.append(safe_call())) for _ in range(8)]


def safe_call():
    try:
        return srv.mcp_result(slow_fn)
    except Exception as e:  # noqa: BLE001 - test records failures too
        return f"FAILED: {e}"


for t in threads:
    t.start()
for t in threads:
    t.join()

assert results == ["ok"] * 8, results
assert max_active == 1, f"calls overlapped: max_concurrent={max_active}"
print(f"8. mcp_result serializes concurrent calls OK (8 threads, max_concurrent={max_active})")

# 9. HTTP alias endpoint normalizes questions before delegating to systemone
import asyncio

captured = {}


HEADER_DEFAULT = object()


async def fake_systemone(request, authorization=HEADER_DEFAULT):
    captured["payload"] = json.loads((await request.receive())["body"])
    captured["authorization"] = authorization
    return "ok"


srv.systemone = fake_systemone


async def run_decision(payload, authorization=None):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    return await srv.decisions(srv.Request({"headers": headers}, receive))


out = asyncio.run(
    run_decision(
        {
            "state": "hi",
            "questions": {"q1": {"type": "choice", "prompt": "p", "choices": ["a", "b"]}},
        },
        authorization="Bearer test",
    )
)
assert out == "ok", out
assert captured["payload"]["questions"]["q1"]["criteria"] == {"a": "a", "b": "b"}, captured
assert captured["authorization"] == "Bearer test", captured
print("9. /v1/decisions expands aliases and forwards authorization OK")

out = asyncio.run(run_decision({"state": "hi", "questions": {"q1": {"type": "score", "prompt": "p"}}}))
assert out == (
    {"detail": "questions[q1].criteria is required for type 'score'"},
    400,
), out
print("10. /v1/decisions returns 400-style detail on bad questions OK")

print()
print("ALL CHECKS PASSED")
