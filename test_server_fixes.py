
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
_mod("mcp.server.transport_security",
    TransportSecuritySettings=lambda **k: types.SimpleNamespace(**k))
_mod("uvicorn", run=lambda *a, **k: None)
_mod("fastapi")
_mod("fastapi.responses", FileResponse=object, Response=object)

import importlib.util

spec = importlib.util.spec_from_file_location("srv", "server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

# 1. choice with array criteria (the exact shape that crashed in fix2.log)
out = srv.normalize_questions(
    {"q1": {"type": "choice", "prompt": "Which backend?", "choices": ["CPU", "CUDA", "TPU"]}}
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
    {"q1": {"type": "score", "prompt": "How rude 0-3?", "criteria": ["0", "1", "2", "3"]}}
)
assert out["q1"]["criteria"] == ["0", "1", "2", "3"]
print("3. score array passthrough OK")

# 4. choice object criteria via aliases
out = srv.normalize_questions(
    {"backend": {"type": "choice", "prompt": "Which?", "choices": {"CPU": "processor", "CUDA": "gpu"}}}
)
assert out["backend"]["criteria"] == {"CPU": "processor", "CUDA": "gpu"}
print("4. choice object via aliases OK")

# 5. mcp_result surfaces the message instead of redacting
try:
    srv.mcp_result(lambda: (_ for _ in ()).throw(
        ToolError("invalid_questions", "criteria must be an object")))
    raise SystemExit("should have raised")
except srv.McpToolError as e:
    payload = json.loads(str(e))
    assert payload == {"error": "invalid_questions", "message": "criteria must be an object"}, payload
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

print()
print("ALL CHECKS PASSED")
