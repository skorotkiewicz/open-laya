export type Question =
  | { type: "noul"; instructions: string }
  | { type: "choice"; instructions: string; criteria: string[] | Record<string, string> }
  | { type: "score"; instructions: string; criteria: string[] };

export interface Answer {
  type: "noul" | "choice" | "score";
  noul?: number;
  choice?: string;
  score?: number;
  confidence: number;
  probabilities?: Record<string, number>;
}

export interface DecisionResult {
  model: string;
  answers: Record<string, Answer>;
  routing: { model: string; reason: string };
}

export async function decide(
  state: unknown,
  questions: Record<string, Question>,
): Promise<DecisionResult> {
  const baseUrl = (process.env.LAYA_BASE_URL ?? "http://192.168.0.124:8000").replace(/\/$/, "");
  const apiKey = process.env.LAYA_API_KEY;
  const response = await fetch(`${baseUrl}/v1/systemone`, {
    method: "POST",
    redirect: "error",
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
    },
    body: JSON.stringify({ state, questions }),
  });

  if (!response.ok) {
    throw new Error(`Laya HTTP ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<DecisionResult>;
}
