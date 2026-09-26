# USAGE.md

Example usages for the Laya server (`server.py`) and its MCP tools.

Start the server first:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install 'laya[serve,mcp]'
python server.py
```

---

## HTTP API

### Simple decision (noul = yes/no question)

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"Please refund my order","questions":{"refund":{"type":"noul","instructions":"Does the customer request a refund?"}}}' \
  http://localhost:8000/v1/decisions
```

Response (trimmed):

```json
{
  "answers": {
    "refund": {"type": "noul", "noul": 0.02, "confidence": 0.98}
  },
  "routing": {"model": "english", "reason": "English Latin text"}
}
```

### Pick a checkpoint explicitly

Omit `model` for automatic language routing; set a known one to pin it:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"model":"typed-decisions","state":"Please refund me","questions":{"refund":{"type":"noul","instructions":"Is a refund requested?"}}}' \
  http://localhost:8000/v1/decisions
```

Known checkpoints: `english`, `multilingual`, `typed-decisions`.

### Score question (0–3 scale)

`score` questions require `criteria`:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"You people are useless, I want my money back NOW","questions":{"anger":{"type":"score","instructions":"How angry is this customer?","criteria":["0","1","2","3"]}}}' \
  http://localhost:8000/v1/decisions
```

### Choice question

Array `criteria` are expanded to a label→description object (`"a"` → `{"a": "a"}`):

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"The build is broken on main, CI fails","questions":{"topic":{"type":"choice","instructions":"What is this about?","choices":["billing","technical_help","refund"]}}}' \
  http://localhost:8000/v1/decisions
```

### Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/systemone` | Native decision endpoint |
| `POST /v1/decisions`, `POST /decisions` | Aliases |
| `GET /health` | Lists loaded checkpoints |
| `POST /mcp` | MCP streamable HTTP endpoint |

### Server options

- `LAYA_PRELOAD=1` — load all checkpoints at startup (otherwise lazy; first request may download weights from Hugging Face)
- `LAYA_API_KEY=secret` — require `Authorization: Bearer secret` on both HTTP and MCP
- `LAYA_HOST`, `LAYA_PORT` — bind address (default `0.0.0.0:8000`)

---

## MCP tools

Connect any MCP client to `http://127.0.0.1:8000/mcp` (see README for client config). Four tools are exposed:

### `laya_status` — server/checkpoint health

No arguments. Returns device (`cuda`), loaded checkpoints, package versions.

### `laya_predict` — answer typed questions

Question types: `noul` (yes/no), `score` (graded), `choice` (pick one).

```json
{
  "state": {"text": "Buy now! Free crypto!"},
  "questions": {
    "spam": {"type": "noul", "prompt": "This message is spam."},
    "severity": {"type": "score", "prompt": "How bad is this 0-3?", "criteria": ["0", "1", "2", "3"]},
    "topic": {"type": "choice", "prompt": "What is this?", "choices": ["ad", "support", "other"]}
  }
}
```

Aliases accepted: `prompt`/`question`/`text` for `instructions`; `choices`/`options` for `criteria`.

### `laya_route` — which checkpoint will handle a question?

Same arguments as `laya_predict`; returns the routing decision (script/language detection + model) without running inference.

### `laya_preset` — ready-made guard pipelines

```json
{"preset": "moderation", "state": {"text": "great post, check my page for free crypto"}}
```

| Preset | Answers |
|---|---|
| `moderation` | toxic, harassment, threat, spam, severity |
| `guard` | jailbreak, prompt_injection, sensitive_data, harm_severity |
| `triage` | intent, is_urgent, frustration, refund_requested, churn_risk |
| `model_router` | which checkpoint should handle the request |

---

## Tests

Regression tests for the MCP schema handling (no server or GPU needed, run from the repo root):

```sh
python3 tests/test_server_fixes.py
```
