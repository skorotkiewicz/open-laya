# Laya server

A local HTTP API for Laya decisions, with a Tetris game that can ask Laya to place a piece.

From the repository root:

```sh
python -m pip install -e ./laya-src fastapi uvicorn
./laya/server.py
```

Open [Tetris](http://localhost:8000/tetris), or send a decision request:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"Please refund my order","questions":{"refund":{"type":"noul","instructions":"Does the customer request a refund?"}}}' \
  http://localhost:8000/v1/decisions
```

This adapter uses Laya's maintained `laya.serve` API. `POST /v1/systemone` is the native endpoint; `/v1/decisions` and `/decisions` are aliases. Laya chooses a checkpoint by language unless you set a known `model` in the request. `GET /health` lists loaded checkpoints.

The first decision can download weights from Hugging Face. Set `LAYA_PRELOAD=1` to load all checkpoints at startup. For protected inference, set `LAYA_API_KEY`; decision requests then need `Authorization: Bearer <key>`.
