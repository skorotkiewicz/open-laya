#!/usr/bin/env python3
"""Jev-compatible HTTP API for Laya 0.3.6.

Run with ./server.py or python server.py (requires fastapi, uvicorn, laya).
POST /v1/decisions (or /decisions) accepts state and typed questions.
GET /route previews routing without loading weights; POST /route accepts
questions or a preset. GET /health reports status. GET /presets lists built-ins.

Examples (replace localhost with your server address):
    curl http://localhost:8000/health
    curl -H 'Content-Type: application/json' -d '{"model":"typed-decisions","state":"Please refund me","questions":{"refund":{"type":"noul","instructions":"Is a refund requested?"}}}' http://localhost:8000/v1/decisions

The Router selects a checkpoint from the Hugging Face bundle by language.
Request fields: model selects a checkpoint, task selects a workflow, preset
replaces questions, and shortlist_k uses the selected model's encoder to rank
choice labels before scoring. LAYA_AUTO_TASK_DETECTION=1 opts in to workflow
matching. LAYA_PRELOAD=1 warms every checkpoint at startup.

Model management requires LAYA_ADMIN_TOKEN and a Bearer token. Use a trusted
network or TLS, since HTTP sends the token in cleartext:
    curl -H "Authorization: Bearer $LAYA_ADMIN_TOKEN" -H 'Content-Type: application/json' -d '{"names":["english","multilingual"]}' http://localhost:8000/models/preload
    curl -X DELETE -H "Authorization: Bearer $LAYA_ADMIN_TOKEN" http://localhost:8000/models/english
Use /models/all to unload every checkpoint. LAYA_DEVICE, LAYA_MAX_LOADED,
LAYA_DEFAULT and Hugging Face cache/offline variables retain their usual meanings.
"""

from __future__ import annotations

import os
import secrets
import threading
from pathlib import Path
from typing import Any

import anyio
import laya
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

_predict_lock = threading.Lock()  # One forward pass at a time per process.

# Router manages checkpoint downloads, caching and LRU eviction itself.
router = laya.Router(
    device=os.environ.get("LAYA_DEVICE") or None,
    max_loaded=int(os.environ.get("LAYA_MAX_LOADED", "1")),
    default=os.environ.get("LAYA_DEFAULT", "english"),
    auto_task_detection=os.environ.get("LAYA_AUTO_TASK_DETECTION", "").lower() in ("1", "true", "yes", "on"),
    preload=os.environ.get("LAYA_PRELOAD", "").lower() in ("1", "true", "yes", "on"),
)
PRESETS = {
    "triage": laya.triage_questions,
    "email": laya.email_questions,
    "guard": laya.guard_questions,
    "moderation": laya.moderation_questions,
    "router": laya.router_questions,
}

app = FastAPI(title="Laya Decisions API", version="1.1.0")


def predict(state: str | dict | list, questions: dict, model: str | None,
            task: str | None, lang: str | None, shortlist_k: int | None) -> dict:
    with _predict_lock:
        if shortlist_k is None:
            result = router.predict(state, questions, model=model, task=task, lang=lang)
        else:
            # Shortlist with the selected checkpoint's own encoder, then score once.
            decision = router.route(state, questions, model=model, task=task, lang=lang)
            agent = router.load(decision["model"])
            result = laya.predict_shortlist(
                agent, state, questions, laya.embed_fn_from_agent(agent), k=shortlist_k
            )
            result["routing"] = dict(decision)
        result["model"] = "laya"
        return result


class Question(BaseModel):
    type: str
    instructions: str = Field(min_length=1)
    criteria: Any = None


class DecisionRequest(BaseModel):
    state: str | dict | list
    questions: dict[str, Question] | None = None
    preset: str | None = None
    model: str | None = None
    task: str | None = None
    lang: str | None = None
    shortlist_k: int | None = Field(default=None, ge=1)


class PreloadRequest(BaseModel):
    names: list[str] | None = None


def validate_questions(questions: dict[str, Question]) -> None:
    for name, question in questions.items():
        kind, criteria = question.type, question.criteria
        if kind not in ("noul", "choice", "score"):
            raise HTTPException(422, detail={"error": f"question {name!r}: unknown type {kind!r}"})
        if kind == "choice" and (not isinstance(criteria, (dict, list)) or not criteria):
            raise HTTPException(422, detail={"error": f"question {name!r}: choice requires criteria"})
        if kind == "score" and (not isinstance(criteria, list) or not criteria):
            raise HTTPException(422, detail={"error": f"question {name!r}: score requires a rubric list"})
        if kind == "choice" and isinstance(criteria, list) and (
            not all(isinstance(item, str) for item in criteria) or len(set(criteria)) != len(criteria)
        ):
            raise HTTPException(422, detail={"error": f"question {name!r}: choice labels must be unique strings"})


def request_questions(req: DecisionRequest) -> dict:
    if (req.questions is None) == (req.preset is None):
        raise HTTPException(422, detail={"error": "provide exactly one of questions or preset"})
    if req.preset is not None:
        if req.preset not in PRESETS:
            raise HTTPException(422, detail={"error": f"unknown preset {req.preset!r}"})
        return PRESETS[req.preset]()
    if not req.questions:
        raise HTTPException(422, detail={"error": "questions must not be empty"})
    validate_questions(req.questions)
    return {name: question.model_dump() for name, question in req.questions.items()}


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = os.environ.get("LAYA_ADMIN_TOKEN")
    if not token:
        raise HTTPException(503, detail={"error": "set LAYA_ADMIN_TOKEN to enable model management"})
    if not authorization or not secrets.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, detail={"error": "admin token required"},
                            headers={"WWW-Authenticate": "Bearer"})


def change_models(action: str, value: Any = None) -> None:
    # Do not evict a checkpoint while a request is using it.
    with _predict_lock:
        getattr(router, action)(value)


@app.get("/tetris", include_in_schema=False)
def tetris() -> FileResponse:
    return FileResponse(Path(__file__).with_name("tetris.html"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok", "model": "laya", "mode": "router",
        "loaded": bool(router.loaded), "checkpoints_loaded": router.loaded,
        "max_loaded": router.max_loaded,
    }


@app.get("/route")
def route(state: str | None = None, model: str | None = None,
          task: str | None = None, lang: str | None = None) -> dict:
    try:
        return dict(router.route(state or {}, {}, model=model, task=task, lang=lang))
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc


@app.post("/route")
def route_request(req: DecisionRequest) -> dict:
    questions = request_questions(req)
    try:
        return dict(router.route(req.state, questions, model=req.model, task=req.task, lang=req.lang))
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc


@app.get("/presets")
def presets() -> list[str]:
    return list(PRESETS)


@app.get("/presets/{name}")
def preset(name: str) -> dict:
    if name not in PRESETS:
        raise HTTPException(404, detail={"error": f"unknown preset {name!r}"})
    return PRESETS[name]()


@app.get("/models", dependencies=[Depends(require_admin)])
def models() -> dict:
    return {"available": list(router.models), "loaded": router.loaded, "max_loaded": router.max_loaded}


@app.post("/models/preload", dependencies=[Depends(require_admin)])
async def preload(req: PreloadRequest) -> dict:
    if req.names is not None and not req.names:
        raise HTTPException(422, detail={"error": "names must not be empty; omit to preload all"})
    try:
        await anyio.to_thread.run_sync(change_models, "preload", req.names)
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    return {"loaded": router.loaded, "max_loaded": router.max_loaded}


@app.delete("/models/{name}", dependencies=[Depends(require_admin)])
async def unload(name: str) -> dict:
    try:
        await anyio.to_thread.run_sync(change_models, "unload", None if name == "all" else name)
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    return {"loaded": router.loaded}


@app.post("/v1/decisions")
@app.post("/decisions")  # Jev alias
async def decisions(req: DecisionRequest) -> JSONResponse:
    questions = request_questions(req)
    try:
        result = await anyio.to_thread.run_sync(
            predict, req.state, questions, req.model, req.task, req.lang, req.shortlist_k
        )
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(500, detail={"error": f"inference failed: {exc}"}) from exc
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("LAYA_HOST", "0.0.0.0"),
                port=int(os.environ.get("LAYA_PORT", "8000")))
