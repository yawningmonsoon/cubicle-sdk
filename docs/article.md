# Your trading agent is hallucinating its backtest

*Cubicle: anti-hallucination trading for AI agents.*

Ask a language model about a trading setup and you get fluent, confident prose. It names an instrument nobody
verified, at a price nobody checked, with a win rate from a backtest nobody ran. A person reading that can shrug. An
agent with a wallet acts on it.

We spent the last weeks building the opposite, and this is what it does, what it refuses to do, and what we measured
when we pointed it at three strategies everybody has seen.

## The failure, concretely

Someone pastes a chart screenshot into a chat and asks "is this a good setup?". The model reads "RSI 74", "range
high", a ticker, and writes three paragraphs. Every number in those paragraphs is one of three things:

- read off the picture, and possibly misread;
- computed from what was read, which makes it a guess about a guess;
- made up.

The reader cannot tell which is which. Neither can the agent that consumes the answer.

The same happens with a strategy found online. "This opening range breakout has a 68% win rate." On which market?
Which bar size? Which stop? Over which months? The claim arrives without the parts that would let anyone check it.

## What Cubicle does instead

Three rules, enforced in code rather than promised in a prompt.

**1. Take it apart before saying anything about it.** Whatever is posted, a rule in words, a Pine script, a chart, is
first turned into a dossier. Each finding is marked as an *observation* (read or measured), an *inference* (computed
from what was read, and said to be a guess) or an *unknown* (with what would settle it). Each has an id, so an answer
can cite `E4` instead of asserting. A nine-line checklist says what a complete strategy needs: market, bar size,
trigger, direction, stop, target, when it stands aside, whether its numbers match the tape, whether it was ever run.

**2. A reading never claims an execution.** A script that was read was not run. A chart that was read was not
traded. So the dossier carries a ceiling: a screenshot is an *anecdote*, a rule never run is a *hypothesis*. Nothing
is called a strategy until it has been walked over recorded bars.

**3. Numbers come from the tape or they are withheld.** The rule is compiled into a deterministic state machine (the
same words give the same build) and stepped over a week of real bars on six markets. The house agents answer price
questions from the tape; a sentence carrying a number that neither the trader nor a tool supplied is removed before
it is shown.

The method for the first rule is borrowed, with thanks, from software reverse engineering:
[morluto/rea](https://github.com/morluto/rea) teaches agents to separate observation from inference from unknown
when they take a binary apart. A trading strategy somebody posted deserves the same suspicion as a binary somebody
shipped.

## What happened when we ran it

On 12 October 2026 a brand-new free account, minted with one command, rebuilt three textbook rules and ran each on
the trailing week of real bars.

| public rule | market | trades in a week | sum | verdict |
|---|---|---|---|---|
| Opening range breakout | NQ | 5 | +2.5R | needs at least 10 trades to judge |
| RSI-2 pullback | ES | 4 | +1R | needs at least 10 trades to judge |
| Bollinger mean reversion | BTC | 37 | +0.5R | not told apart from chance (p 0.33 to 0.38) |

Two hours later, after BTC fell, the same Bollinger machine read 37 trades and −2R. After that day's New York open
the opening range rule read 6 trades and +1.5R.

None of the three is shown to work. That is the result, and we think it is the useful one. A tool that prints a win
rate for anything you paste is a tool that agrees with you. This one tells an agent "five trades is not evidence" and
"this is not distinguishable from a coin", in a field it can branch on.

It also found things in its own house. The same afternoon it was pointed at our three house agents: one answered a
price question with no number in it, and one, handed a rule, wrote confident words about a rule it had no tools to
read. Both were fixed that day, and the record of it is in the repository's chronicle. We would rather publish that
than a demo that only ever worked.

## Try it

```bash
npm install -g cubicle-sdk
cubicle join my-agent
cubicle reverse strategy.pine
cubicle reconstruct rule.txt --market NQ --accept
```

Four commands, no card, a free key from the first one. The [walkthrough](walkthrough.md) explains every line of
output. People can do the same in the studio at https://cubicle.algotrada.com/deck, with three house agents. Agents
connect to one MCP server, `https://cubicle.algotrada.com/deck/api/mcp`, with the same key.

## What it is not

It is not a signal service and it does not predict. It will not tell you a strategy makes money; it tells you when a
claim is unsupported. The tape covers NQ, ES, YM, BTC, ETH and SOL, nothing else yet. A build uses the conditions
the tape can measure, so it can be an approximation of your words, and the studio says which parts. Plans are paid
on chain in USDG on Robinhood Chain; nobody has to pay to run anything in this article.

If your agent is going to trade, make it prove the strategy first.
