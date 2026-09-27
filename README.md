# Laya server

A local HTTP API for Laya decisions and MCP tools.

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install 'laya[serve,mcp]'
python server.py

LAYA_API_KEY=your-key python server.py 

# .venv/bin/pip install (-q) torch --index-url https://download.pytorch.org/whl/cpu
#  pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu128
# .venv/bin/pip install (-q) 'laya[langchain]'
```

Send a decision request:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"state":"Please refund my order","questions":{"refund":{"type":"noul","instructions":"Does the customer request a refund?"}}}' \
  http://localhost:8000/v1/decisions

# with api key
curl -H 'Content-Type: application/json' -H 'Authorization: Bearer your-key' \
  -d '{"state":"Please refund my order","questions":{"refund":{"type":"noul","instructions":"Does the customer request a refund?"}}}' \
  http://localhost:8000/v1/decisions
```

<details>
  <summary>All at once:</summary>

```sh
curl http://192.168.0.124:8000/v1/decisions -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-api-key" \
  -d '{
    "state": "Help! My payouts have been failing for 3 days.",
    "questions": {
      "is_urgent": {
        "type": "noul",
        "instructions": "Does this message convey urgency?",
        "criteria": {
          "true": "Explicitly time-sensitive",
          "false": "No urgency expressed"
        }
      },
      "department": {
        "type": "choice",
        "instructions": "Which team should handle this?",
        "criteria": {
          "billing": "Payments, invoicing, refunds",
          "technical": "Bugs, outages, integrations",
          "sales": "Pricing, upgrades, new accounts"
        }
      },
      "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": ["Calm", "Frustrated", "Very angry"]
      }
    }
  }'
```

<details>
  <summary>Output:</summary>

```json
{
  "model": "laya-rl-agent",
  "answers": {
    "is_urgent": {
      "type": "noul",
      "noul": 0.7875,
      "confidence": 0.7875,
      "answer_confidence": 0.7875,
      "action": {
        "act_probability": 1.0
      }
    },
    "department": {
      "type": "choice",
      "choice": "billing",
      "probabilities": {
        "billing": 0.8362,
        "technical": 0.0941,
        "sales": 0.0698
      },
      "confidence": 0.4924,
      "answer_confidence": 0.8362,
      "action": {
        "act_probability": 1.0
      }
    },
    "frustration": {
      "type": "score",
      "score": 1.0886,
      "legend": {
        "0": "Calm",
        "1": "Frustrated",
        "2": "Very angry"
      },
      "probabilities": {
        "0": 0.0318,
        "1": 0.8478,
        "2": 0.1204
      },
      "confidence": 0.5408,
      "answer_confidence": 0.8478,
      "action": {
        "act_probability": 1.0
      }
    }
  },
  "usage": {
    "input_tokens": 143,
    "output_tokens": 0
  },
  "routing": {
    "model": "english",
    "repo": "convaiinnovations/laya",
    "reason": "English Latin text",
    "detection": {
      "script": "latin",
      "script_profile": {
        "latin": 1.0
      },
      "language": "en",
      "is_english": true,
      "language_undecided": false,
      "diacritic_rate": 0.0,
      "non_latin_fraction": 0.0
    },
    "workflow": null
  }
}
```

</details>
</details>

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
