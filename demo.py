import laya

# Load the model directly from Hugging Face Hub
agent = laya.load("convaiinnovations/laya")

state = {
    "from": "customer@acme.com",
    "subject": "Duplicate billing on March invoice #4411",
    "body": "Hi team, we were billed twice for March. Please refund the duplicate before Friday or we will cancel our plan."
}

questions = {
    "department": {
        "type": "choice",
        "instructions": "Which department should handle this email?",
        "criteria": {
            "billing": "invoices, payments, refunds",
            "technical": "bugs, outages, integrations",
            "sales": "pricing, contracts, demos",
            "other": "everything else"
        }
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this request?",
        "criteria": ["not urgent", "soon", "critical deadline or blocking issue"]
    },
    "churn_risk": {
        "type": "noul",
        "instructions": "Does the user threaten to cancel or switch to a competitor?"
    },
    "is_phishing": {
        "type": "noul",
        "instructions": "Is this email a phishing or scam attempt?"
    }
}

result = agent.predict(state, questions)
answers = result["answers"]

print("Department :", answers["department"]["choice"], f"(confidence: {answers['department']['confidence']:.2f})")
print("Urgency    :", f"{answers['urgency']['score']:.2f} / 2.0")
print("Churn Risk :", f"{answers['churn_risk']['noul']:.1%}")
print("Phishing   :", f"{answers['is_phishing']['noul']:.1%}")

# █████ █████   █████ █████
# █   █ █   █ █ █   █ █   █
# █████ █████   █████ █████
# █   █ █   █ █ █   █ █   █
# █████ █████   █████ █████

# █████████████████████
#########################
# ████.████ . ████.████ #
# █  █ █  █ @ █  █ █  █ #
# ████ ████   ████ ████ #
# █  █ █  █ @ █  █ █  █ #
# ████.████ . ████.████ #
#########################
# █████████████████████
