# cubicle-sdk

**Cubicle: anti-hallucination trading for AI agents.**
Prove any strategy before an agent trades it.

Paste a strategy you found (a rule in words, a TradingView Pine script). Cubicle takes it apart into what is
observed, what is inferred and what is unknown, builds it into a state machine, and runs it over a week of recorded
bars. The number you get back is measured on real tape, not quoted from whoever posted it.

Zero dependencies. Node 18 or newer. MIT.

```bash
npm install -g cubicle-sdk
cubicle join my-agent                                   # a free key, saved to ~/.cubicle/key (0600), never printed
cubicle reverse strategy.pine                           # read, never run: observed / inferred / unknown
cubicle reconstruct rule.txt --market NQ --accept       # build it and run it on the last week of real bars
```

```js
import { Cubicle } from "cubicle-sdk";

const c = new Cubicle();                                // CUBICLE_KEY, or ~/.cubicle/key
const dossier = await c.reverse(pineSource);            // strategy-dossier.v1
const run = await c.reconstruct(rule, { market: "BTC", accept: true });
console.log(run.rehearsal.rehearsal);                   // { receipts, hours, sumR, pValue }
const bars = await c.call("tape", { market: "BTC", tf: "1h", from: "2026-10-10T00:00:00Z", to: "2026-10-11T00:00:00Z" });
```

A refusal is a `CubicleError` with a stable `kind` (`unauthenticated`, `studio_gate`, `plan_required`, `unknown_tool`,
`bad_arguments`) and, when the server gave one, `next`: the step that lifts it. `--accept` (or `accept: true`) is yours
to give: it accepts the rule's parts as read and builds from the gates the tape can measure.

Have a code (a jury's, a partner's)? `cubicle join my-agent --code CODE`, or `cubicle redeem CODE` for an account you
already have: more free turns with the house agents until the code's end date.

The server is one MCP endpoint, `https://cubicle.algotrada.com/deck/api/mcp` (streamable HTTP); `cubicle tools` lists
what it serves. Markets on the tape: NQ, ES, YM, BTC, ETH, SOL. Nothing here is investment advice: the tool tells you
when a claim is unsupported, never that a strategy will make money, and a rehearsal is the past, not a forecast.

The Python package, the walkthrough and the production chronicle live in the same repository:
https://github.com/yawningmonsoon/cubicle-sdk
