# Security

Report a vulnerability privately: open a GitHub security advisory on this repository ("Report a vulnerability"), or
write to the maintainers through https://cubicle.algotrada.com. Please do not open a public issue for it.

What this package does with secrets: your Cubicle key is read from `CUBICLE_KEY` or `~/.cubicle/key` (a file other
users can read is refused), sent only as the bearer to the server you point it at, and never printed, logged or put
in an error. `cubicle join` writes the key with owner-only permissions and never prints it.
