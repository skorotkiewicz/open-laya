#!/usr/bin/env python3
"""Jev-compatible HTTP API for Laya 0.3.6.

Run with ./server.py or python server.py (requires fastapi, uvicorn, laya).
POST /v1/decisions (or /decisions) accepts state and typed questions.
GET /route previews routing without loading weights; GET /health reports status.

Examples (replace localhost with your server address):
    curl http://localhost:8000/health
    curl -H 'Content-Type: application/json' -d '{"model":"typed-decisions","state":"Please refund me","questions":{"refund":{"type":"noul","instructions":"Is a refund requested?"}}}' http://localhost:8000/v1/decisions

The Router selects a checkpoint from the Hugging Face bundle by language.
A known checkpoint name in the request's model field overrides routing.
LAYA_PRELOAD=1 warms every checkpoint at startup. LAYA_DEVICE,
LAYA_MAX_LOADED, LAYA_DEFAULT and Hugging Face cache/offline variables
retain their usual meanings.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import anyio
from laya import Router
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

_predict_lock = threading.Lock()  # One forward pass at a time per process.

# Router manages checkpoint downloads, caching and LRU eviction itself.
router = Router(
    device=os.environ.get("LAYA_DEVICE") or None,
    max_loaded=int(os.environ.get("LAYA_MAX_LOADED", "1")),
    default=os.environ.get("LAYA_DEFAULT", "english"),
    preload=os.environ.get("LAYA_PRELOAD", "").lower() in ("1", "true", "yes", "on"),
)

app = FastAPI(title="Laya Decisions API", version="1.1.0")


def predict(state: str | dict | list, questions: dict, model: str | None, lang: str | None) -> dict:
    with _predict_lock:
        result = router.predict(state, questions, model=model, lang=lang)
        result["model"] = "laya"
        return result


class Question(BaseModel):
    type: str
    instructions: str = Field(min_length=1)
    criteria: Any = None


class DecisionRequest(BaseModel):
    state: str | dict | list
    questions: dict[str, Question] = Field(min_length=1)
    model: str | None = None
    lang: str | None = None


def validate_questions(questions: dict[str, Question]) -> None:
    for name, question in questions.items():
        kind, criteria = question.type, question.criteria
        if kind not in ("noul", "choice", "score"):
            raise HTTPException(422, detail={"error": f"question {name!r}: unknown type {kind!r}"})
        if kind == "choice" and (not isinstance(criteria, (dict, list)) or not criteria):
            raise HTTPException(422, detail={"error": f"question {name!r}: choice requires criteria"})
        if kind == "score" and (not isinstance(criteria, list) or not criteria):
            raise HTTPException(422, detail={"error": f"question {name!r}: score requires a rubric list"})


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok", "model": "laya", "mode": "router",
        "loaded": bool(router.loaded), "checkpoints_loaded": router.loaded,
        "max_loaded": router.max_loaded,
    }


@app.get("/route")
def route(state: str | None = None, model: str | None = None, lang: str | None = None) -> dict:
    return dict(router.route(state or {}, {}, model=model, lang=lang))


@app.post("/v1/decisions")
@app.post("/decisions")  # Jev alias
async def decisions(req: DecisionRequest) -> JSONResponse:
    validate_questions(req.questions)
    questions = {name: q.model_dump() for name, q in req.questions.items()}
    try:
        result = await anyio.to_thread.run_sync(predict, req.state, questions, req.model, req.lang)
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(500, detail={"error": f"inference failed: {exc}"}) from exc
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("LAYA_HOST", "0.0.0.0"),
                port=int(os.environ.get("LAYA_PORT", "8000")))
