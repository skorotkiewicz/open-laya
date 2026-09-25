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

Laya selects a checkpoint by language. Set `"model":"typed-decisions"` in a request to choose one explicitly. `GET /health` shows loaded checkpoints; `GET /presets` lists built-in question sets. Requests also accept `task`, `preset`, and `shortlist_k`.

To manage loaded checkpoints over HTTP, set an admin token before starting the server:

```sh
export LAYA_ADMIN_TOKEN='replace-with-a-long-random-secret'
./laya/server.py
curl -H "Authorization: Bearer $LAYA_ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"names":["english","multilingual"]}' http://localhost:8000/models/preload
curl -X DELETE -H "Authorization: Bearer $LAYA_ADMIN_TOKEN" \
  http://localhost:8000/models/english
```

Inference endpoints do not require a token. Use a trusted network or TLS: plain HTTP exposes the admin token. The first model request can download checkpoint weights from Hugging Face.
