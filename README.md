<p align="center"><img src="docs/assets/cubicle-mark.png" width="96" alt="Cubicle"></p>

<h1 align="center">cubicle-sdk</h1>

<p align="center"><b>Cubicle: anti-hallucination trading for AI agents.</b><br>
Prove any strategy before an agent trades it.</p>

<p align="center">
<a href="LICENSE"><img alt="MIT" src="https://img.shields.io/badge/license-MIT-0d9488"></a>
<img alt="Node 18+" src="https://img.shields.io/badge/node-18%2B-131311">
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-131311">
<img alt="zero dependencies" src="https://img.shields.io/badge/dependencies-0-0d9488">
<a href="https://cubicle.algotrada.com/deck/api/mcp"><img alt="MCP server" src="https://img.shields.io/badge/MCP-39%20tools-d8d2c4"></a>
<img alt="Robinhood Chain" src="https://img.shields.io/badge/settles%20on-Robinhood%20Chain-d8d2c4">
</p>

**An MCP trading toolkit and backtesting client for AI agents**: reverse-engineer a TradingView Pine script or a
strategy you found online, compile it into a deterministic state machine, and backtest it on recorded bars of NQ, ES,
YM, BTC, ETH and SOL, with the result checked against a random null instead of quoted. For agent builders (Claude,
Cursor, any MCP client), quant hobbyists and traders who want an agent that refuses to trade what it cannot reproduce.

Paste a strategy you found (a rule in words, a Pine script, a chart). Cubicle takes it apart into what is
observed, what is inferred and what is unknown, builds it into a state machine, and runs it over recorded bars.
The number you get back is measured on real tape, not quoted from whoever posted it.

![reverse-engineer, forge and rehearse a public strategy from a terminal](chronicle/2026-10-12-reverse-engineer/reconstruct.gif)

Part of [Cubicle](https://cubicle.algotrada.com), by AlgoTrada. MIT. Two packages with the same verbs: JavaScript (`js/`, Node 18+, zero dependencies) and Python (3.10+, standard library only).

---

## Start: an agent, three lines

```bash
npm install -g cubicle-sdk                             # Node 18+, zero dependencies (js/)
# or: pip install git+https://github.com/yawningmonsoon/cubicle-sdk     (Python 3.10+, standard library only)
cubicle join my-agent                                  # a free key, saved to ~/.cubicle/key (0600), never printed
cubicle reverse examples/strategies/opening-range-breakout.pine
cubicle reconstruct examples/strategies/opening-range-breakout.txt --market NQ --accept
```

Both packages install the same `cubicle` command and speak to the same server. New here? Read the
[walkthrough](docs/walkthrough.md) (ten minutes, every line of output explained) and the
[article](docs/article.md) on why this exists. Were you given a code? `cubicle join my-agent --code CODE`, or
`cubicle redeem CODE` for an account you already have: more free turns with the house agents.

```python
from cubicle_sdk.mcp import Cubicle

c = Cubicle()                                          # reads CUBICLE_KEY or ~/.cubicle/key
dossier = c.reverse(open("strategy.pine").read())      # observed / inferred / unknown, the checklist, the ceiling
bars = c.call("tape", market="BTC", tf="1h", **{"from": "2026-10-10T00:00:00Z", "to": "2026-10-11T00:00:00Z"})
```

A refusal is a `CubicleError` with a stable `kind` (`unauthenticated`, `studio_gate`, `plan_required`,
`unknown_tool`, `bad_arguments`) and, when the server gave one, `next`: the step that lifts it.

## Start: a person

Open **https://cubicle.algotrada.com/deck**, sign in with your email (a magic link) or a key, and post the strategy
in the studio. `/reverse` takes apart what you posted, `/forge` builds it, `/rehearse` runs it on the tape. The key
you sign in with is the same key an agent uses: one identity for both.

## Reconstruct a strategy from the internet

```bash
cubicle reconstruct examples/strategies/rsi2-pullback.txt --market ES --accept
```

The chain is the studio's own and the server decides every gate; the script only follows it:
`reverse` (nothing is run) → `workflow_read` (the seven parts, from the rule's own words) → the studio's moves
(accept the parts, choose how it is measured) → `forge` → `rehearse` on the last week of real bars.

Measured on production, 2026-10-12, as a brand-new free account
([the chronicle](chronicle/2026-10-12-reverse-engineer/README.md)):

| public rule | market | trades in 168 h | sum | the studio's gate |
|---|---|---|---|---|
| Opening range breakout | NQ | 5 | +2.5R | at least 10 trades are needed to judge it |
| RSI-2 pullback | ES | 4 | +1R | at least 10 trades are needed to judge it |
| Bollinger mean reversion | BTC | 37 | +0.5R | not yet told apart from chance (p 0.33 to 0.38) |

The window is the trailing week, so the numbers move: an hour later, after a fall in BTC, the same Bollinger rule
read 37 trades, −2R, p 0.67. None of the three is shown to work. That is the result: a week of bars does not support any of them yet, and
the tool says so instead of printing a win rate.

## The dossier

`reverse` answers with one JSON object (`strategy-dossier.v1`):

- **route**: what was posted and which tool reads it first. A chart is read then checked against the tape; a
  script is read, never run; words go to the reader.
- **findings**: each is an `observation` (read or measured), an `inference` (computed from what was read, and
  said to be a guess) or an `unknown` (with what would settle it). Each has an id (`E1`, `E2`, …) to cite.
- **checklist**: market, bar size, trigger, direction, stop, target, stand aside, do its numbers match the
  tape, was it run over recorded bars. Each is answered, partial or unresolved.
- **ceiling**: a screenshot is an `anecdote`; a rule that was never run is a `hypothesis`.

The method is adapted from [morluto/rea](https://github.com/morluto/rea) (MIT), whose subject is shipped
software: route the target first, summary first, separate observation from inference from unknown, and never
let a static reading claim an execution. No code was taken.

## Connect from any app

One server, streamable HTTP: `https://cubicle.algotrada.com/deck/api/mcp`. Listing its tools needs no key; a
call needs `Authorization: Bearer <your Cubicle key>`.

```bash
# Claude Code
claude mcp add --transport http cubicle https://cubicle.algotrada.com/deck/api/mcp --header "Authorization: Bearer $CUBICLE_KEY"
```

```json
{ "mcpServers": { "cubicle": { "type": "http", "url": "https://cubicle.algotrada.com/deck/api/mcp",
    "headers": { "Authorization": "Bearer YOUR_CUBICLE_KEY" } } } }
```

Cursor, VS Code and Cline take that shape in their MCP settings (field names differ slightly between clients:
check yours). Claude Desktop and other stdio-only clients bridge with
`npx mcp-remote https://cubicle.algotrada.com/deck/api/mcp --header "Authorization: Bearer ${CUBICLE_KEY}"`.
Anything else: POST JSON-RPC 2.0 (`initialize`, `tools/list`,
`tools/call`), which is all `cubicle_sdk/mcp.py` does.

The tools, as the live server lists them: `python -m cubicle_sdk.mcp tools` (39 on 2026-10-12: the studio chain,
the tape, plans, strategies, copy-trading, vaults on Robinhood Chain).

### Where the server is listed

Read keyless from each channel on 2026-10-12; the manifest is [`server.json`](server.json).

| channel | state |
|---|---|
| Official MCP registry | listed as `com.algotrada.cubicle/cubicle` (the registry holds 1.1.0, the server reports 1.0.0) |
| Glama | listed: https://glama.ai/mcp/connectors/com.algotrada.cubicle/cubicle |
| PulseMCP | ingests the official registry; not readable without a browser |
| Smithery | not listed yet |
| mcp.so | not listed yet |
| a2aregistry.org | not listed yet (the card is served at `/.well-known/agent-card.json`) |

### On the coordination layer

Cubicle's three services (studio, candles, copy) are listed as hireable sellers on the Taifoon coordination layer,
each with an ERC-8004 identity, so another agent can find and hire them where agents look for sellers. Every sale
through the layer is one tracked run on one ledger; its public summary is
https://api.taifoon.dev/coordination/sale-run.json. What is **not** live: a trader being paid for a strategy they
published. That path is designed, not open; nothing here should be read as an earnings offer.

---

## The lab counters

Seven runnable checks for a claim you already have numbers for. Stdlib only, deterministic, JSON out, each with a `--self-test`.

Every one answers a documented way that trading research fools itself.

| Counter | Answers |
|---|---|
| `null_panel` | Does this beat always-up, seeded random, with-prev, and buy-and-hold **on the same window**? |
| `deflated_sharpe` | Does the Sharpe survive the number of variants actually tried? |
| `calibration` | Do the stated probabilities track observed frequency — and do they carry information? |
| `pushback` | Does the decision survive pressure that carries no new evidence? |
| `pass_k` | Do identical reruns agree, and does the score exceed its own dispersion? |
| `corpus_flag` | Does the evaluation window sit before or after the model's cutoff? |
| `one_switch` | Toggle one input — if the alpha vanishes, it was never alpha. |

```bash
python3 -m cubicle_sdk.lab.null_panel --file candles.jsonl
python3 -m cubicle_sdk.lab.calibration --file forecasts.jsonl
python3 -m cubicle_sdk.lab.deflated_sharpe --sr 2.5 --trials 100 --obs 1250
```

Each prints one JSON object. Each returns exit `0` clean, `2` on a typed
error — so a caller routes on `error.kind`, never on message text.

### Three rules the counters enforce

**Nulls before trust.** No harness result counts until the null panel ran on
the same window. A strategy that barely beats `always_up` rediscovered the
drift.

**Trials are counted, not recalled.** With five years of data, ~45 independent
configurations almost guarantees an in-sample Sharpe of 1.0 whose true
out-of-sample Sharpe is zero. If an agent iterates, N explodes silently.

**Calibration alone is not enough.** A forecaster that always says the base
rate is *perfectly calibrated* and carries zero information. `calibration`
reports Murphy's resolution beside reliability so that case cannot pass.

---

## The gate ladder

Seven rungs. Exactly one may carry a price.

```python
from cubicle_sdk import GateState

GateState.LIVE.may_be_priced               # False — dispatching real money is not expectancy
GateState.RESELLER_ELIGIBLE.may_be_priced  # True
GateState.parse("Certifiedd")              # GateState.DRAFT — fails closed
```

**Unknown input degrades to `Draft`**, the least-privileged rung, rather than
raising. Every caller of `parse` is deciding what an algo may do; an exception
tempts callers into `or SOMETHING_PERMISSIVE`. A typo, a truncated file, or a
future rung this version does not know about all fail in the safe direction.

## The honesty block

`None` means **not run** — never *passed*.

```python
from cubicle_sdk import HonestyBlock

HonestyBlock().unmeasured()
# ['determinism', 'one_switch', 'pass_k', 'corpus']

HonestyBlock(corpus="pre_cutoff").corpus_is_clean   # False
```

A pre-cutoff window is contaminated. Directional accuracy collapses from
99.26% to 52.94% across a model's training cutoff, and instructing a model to
respect an artificial cutoff does not work — roughly 98% accuracy is retained.
Only a data-layer control counts.

`SignedReceipt.verify_shape()` reports structural problems. **It does not
verify cryptography** and says so: a well-formed envelope with a forged
signature passes that check.

---

## FAQ

**Is this a trading bot?** No. It is the part that comes before one: it tells you whether a strategy is supported by
recorded data. A strategy can then be hired to run a vault you own, under a signed, capped mandate.

**Can I backtest a TradingView Pine script with it?** It reads Pine statically (entries, sides, stops, targets,
sessions, repaint risks) and never runs it. To test it, write the rule in words (or let the studio read it) and
`cubicle reconstruct`: the test runs on our own recorded bars, not TradingView's.

**Which AI clients work?** Any MCP client over streamable HTTP: Claude Code, Claude Desktop (through `mcp-remote`),
Cursor, VS Code, Cline. Or this SDK from Node or Python.

**Does it give signals or predictions?** No. It never gives a direction or a price target. The expected-range
indicator it draws is a size, never a direction.

**What does it cost?** Signing up and running the examples is free. Plans are paid on chain in USDG on Robinhood Chain.

## Scope limits, stated plainly

- **Not investment advice.** These tools tell you when a claim is *unsupported*. They never tell you a strategy
  will make money, and a rehearsal is the past, not a forecast.
- **A forge is built from the gates the tape can measure.** When a rule names something the tape cannot
  evaluate, the studio says which part and builds an approximation only if you choose it.
- **Tape coverage is NQ / ES / YM futures and BTC / ETH / SOL.** No equities, no options.
- **No signer and no session driver.** Receipts are signed venue-side; a client-side signer would let anything
  mint one. `SignedReceipt.verify_shape()` checks structure, not cryptography.
- **Pine is read by pattern, not parsed.** Multi-line calls and functions that wrap `strategy.entry` are
  undercounted; a drawing-only indicator yields mostly unknowns, which is the honest answer.
- **Free sign-ups are limited** to a few a day per client.

## Tests

```bash
python3 -m pytest tests/ -q
```

The MCP client against a local stand-in server (protocol shape, refusals as kinds, the key never printed), the
ladder invariants, the honesty-block semantics and every counter's self-test.

## License

MIT.
