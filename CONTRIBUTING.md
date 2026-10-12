# Contributing

- Both packages stay dependency-free: Node's standard library in `js/`, Python's in `cubicle_sdk/`.
- The two packages keep the same verbs and the same `cubicle` command. A change to one lands in the other.
- Tests run without a network, against a local stand-in server: `cd js && node --test test.mjs` and `python3 -m pytest tests -q`.
- A number in the docs comes from a command that was run, with the date it was run. Nothing is promised that the code does not do.
- No signals, no direction, no price targets: the tools say when a claim is unsupported, never that a strategy will make money.
