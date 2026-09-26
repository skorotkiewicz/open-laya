import { decide } from "./client.ts";

const result = await decide("Please refund my duplicate charge", {
  department: {
    type: "choice",
    instructions: "Which team should handle this request?",
    criteria: {
      billing: "charges, invoices, payments, and refunds",
      technical: "bugs, outages, and API problems",
      sales: "pricing, demos, and new purchases",
    },
  },
  refund: {
    type: "noul",
    instructions: "Does the customer request a refund?",
  },
});

console.log(JSON.stringify(result, null, 2));
