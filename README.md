# Laya server

A local HTTP API for Laya decisions and MCP tools.

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install 'laya[serve,mcp]'
python server.py
```

Send a decision request:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"Please refund my order","questions":{"refund":{"type":"noul","instructions":"Does the customer request a refund?"}}}' \
  http://localhost:8000/v1/decisions
```

This adapter uses Laya's maintained `laya.serve` API. `POST /v1/systemone` is the native endpoint; `/v1/decisions` and `/decisions` are aliases. Laya chooses a checkpoint by language unless you set a known `model` in the request. `GET /health` lists loaded checkpoints.

The first decision can download weights from Hugging Face. Set `LAYA_PRELOAD=1` to load all checkpoints at startup. Set `LAYA_API_KEY` to require a bearer token for both decision requests and MCP.

Connect an MCP client on the same machine:

```json
{
  "laya": {
    "type": "http",
    "url": "http://127.0.0.1:8000/mcp",
    "headers": {"Authorization": "Bearer <your LAYA_API_KEY>"},
    "directTools": true
  }
}
```

Omit `headers` if `LAYA_API_KEY` is unset. MCP exposes `laya_status`, `laya_route`, `laya_predict`, and `laya_preset` on the same Router as the decision API.
