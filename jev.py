import requests
import json
import os

# The model answers narrow, typed questions about the state. Your code owns the workflow.
response = requests.post(
  url="https://openrouter.ai/api/alpha/decisions",
  headers={
    "Authorization": "Bearer " + os.environ['API_KEY'],
    "Content-Type": "application/json",
    "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
    "X-OpenRouter-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
  },
  data=json.dumps({
    "model": "typesafe/jev-1.13",
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
  })
)

answers = response.json()["answers"]
# noul is a probability from 0 (no) to 1 (yes); choice and score carry the full distribution.
print(answers["is_urgent"]["noul"])
print(answers["department"]["choice"], answers["department"]["probabilities"])
print(answers["frustration"]["score"])

# output:
# 0.95
# billing {'billing': 0.87, 'sales': 0, 'technical': 0.13}
# 1.05

if answers["is_urgent"]["noul"] > 0.8 and answers["department"]["choice"] == "billing":
  pass  # escalate_to_billing(...)
