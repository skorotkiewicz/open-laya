import { decide } from "./client.ts";

const refund = await decide("Please refund me", {
    refund: {
      type: "noul",
      instructions: "Is a refund requested?",
    },
  },
  { model: "typed-decisions" },
);
console.log("refund:", JSON.stringify(refund.answers.refund));

const anger = await decide("You people are useless, I want my money back NOW", {
  anger: {
    type: "score",
    instructions: "How angry is this customer?",
    criteria: ["0", "1", "2", "3"],
  },
});
console.log("anger:", JSON.stringify(anger.answers.anger));

const topic = await decide("The build is broken on main, CI fails", {
  topic: {
    type: "choice",
    instructions: "What is this about?",
    criteria: ["billing", "technical_help", "refund"],
  },
});
console.log("topic:", JSON.stringify(topic.answers.topic));

const german = await decide("Der Kunde wurde zweimal belastet", {
  department: {
    type: "choice",
    instructions: "Welche Abteilung soll diese Anfrage bearbeiten?",
    criteria: {
      billing: "Rechnungen, Zahlungen, Rückerstattungen und doppelte Abbuchungen",
      technical: "Fehler, Ausfälle und technische Probleme",
      other: "alles andere",
    },
  },
});
console.log(JSON.stringify(german.answers.department));
