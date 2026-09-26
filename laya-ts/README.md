# laya-ts HTTP example

A dependency-free TypeScript client for the remote Laya API. Requires Node 24+.

```sh
LAYA_API_KEY=your-key npm start
```

Override the server URL when needed:

```sh
LAYA_BASE_URL=http://127.0.0.1:8000 LAYA_API_KEY=your-key npm start
```

Run the Snake example interactively or headless:

```sh
LAYA_API_KEY=your-key npm run snake
LAYA_API_KEY=your-key npm run snake -- --ticks 20
```

Use `--url http://host:port` to override `LAYA_BASE_URL`. After five API errors, Snake continues with its built-in heuristic.

Run the multilingual example:

```sh
LAYA_API_KEY=your-key npm run try-ml
```

From the repository root, add `--prefix laya-ts` to npm commands:

```sh
LAYA_API_KEY=your-key npm --prefix laya-ts run snake -- --ticks 20
```

Import the client from `src/client.ts`:

```ts
import { decide } from "./src/client.ts";

const result = await decide("Please refund my order", {
  refund: {
    type: "noul",
    instructions: "Does the customer request a refund?",
  },
});
```
