# laya-ts HTTP example

A dependency-free TypeScript client for the remote Laya API. Requires Node 24+.

```sh
LAYA_API_KEY=your-key npm --prefix laya-ts start
```

Override the server URL when needed:

```sh
LAYA_BASE_URL=http://127.0.0.1:8000 LAYA_API_KEY=your-key npm --prefix laya-ts start
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
