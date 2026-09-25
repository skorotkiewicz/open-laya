#!/usr/bin/env python3
r"""Run Laya's HTTP server with decision aliases and the local Tetris page.

Choose a checkpoint for one request:
    curl -H 'Content-Type: application/json' \
      -d '{"model":"typed-decisions","state":"Please refund me","questions":{"refund":{"type":"noul","instructions":"Is a refund requested?"}}}' \
      http://localhost:8000/v1/decisions

Use english, multilingual, or typed-decisions. Omit model for language routing;
the response's routing.model shows the checkpoint Laya selected.
"""

import os
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse
from laya.serve import create_app

# Keep model loads lazy unless the operator explicitly asks for startup preload.
os.environ.setdefault("LAYA_PRELOAD", "0")
app = create_app()

# Use Laya's own request validation, inference worker, and optional API key.
systemone = next(route.endpoint for route in app.routes if route.path == "/v1/systemone")
app.add_api_route("/v1/decisions", systemone, methods=["POST"], include_in_schema=False)
app.add_api_route("/decisions", systemone, methods=["POST"], include_in_schema=False)


@app.get("/tetris", include_in_schema=False)
def tetris() -> FileResponse:
    return FileResponse(Path(__file__).with_name("tetris.html"))


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("LAYA_HOST", "0.0.0.0"),
                port=int(os.environ.get("LAYA_PORT", "8000")))
