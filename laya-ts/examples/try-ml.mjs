import { decide } from "../src/client.ts";

// Direct predict (Hindi -> multilingual weights)
const direct = await decide(
  { body: "मुझसे दो बार शुल्क लिया गया, कृपया पैसे वापस करें।" },
  {
    department: {
      type: "choice",
      instructions: "Which department should handle this request?",
      criteria: {
        billing: "invoices, payments, refunds",
        technical: "bugs, outages, system errors",
        sales: "pricing, new contracts",
        other: "everything else",
      },
    },
    churn_risk: { type: "noul", instructions: "Does the user threaten to cancel or leave?" },
  }
);
console.log(JSON.stringify(direct, null, 2));

// The server detects the language and returns routing metadata.
const routed = await decide({ body: "Der Kunde wurde zweimal belastet" }, {
  department: {
    type: "choice",
    instructions: "Which department should handle this request?",
    criteria: { billing: "invoices, payments, refunds", technical: "bugs, outages", other: "rest" },
  },
});
console.log("routing:", JSON.stringify(routed.routing));
console.log("answer:", JSON.stringify(routed.answers.department));
