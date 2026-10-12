# Releasing

The repository was made public on 2026-10-12 with a fresh history (step 2 below is done). The npm package is published by the owner (step 1).

## 1. npm (`cubicle-sdk`, from `js/`)

The name `cubicle-sdk` was free on npm on 2026-10-12.

```bash
cd js
node --test test.mjs            # 6 tests against a local stand-in server
npm pack --dry-run              # 5 files, about 7 kB: index.mjs, index.d.ts, cli.mjs, README.md, LICENSE
npm login                       # the owner's npm account (2FA)
npm publish --access public
```

After publishing: `npm install -g cubicle-sdk && cubicle tools` should list the live server's tools.

## 2. The repository

The first commits of this repository carried a registry of private module locations. It is deleted from the tree but
remains in git history, so the repository must not be made public with its history. Publish a fresh history:

```bash
git checkout --orphan public && git add -A && git commit -m "cubicle-sdk v0.2.0"
git branch -M public main && git push --force origin main      # replaces the remote history: irreversible there
gh repo edit yawningmonsoon/cubicle-sdk --visibility public --accept-visibility-change-consequences
```

Keep a local bundle of the old history first: `git bundle create ../cubicle-sdk-private-history.bundle --all`.

## 3. PyPI (optional)

`python -m build && twine upload dist/*`. Until then the README installs from git.

## What to post

- `docs/article.md`: the article ("Your trading agent is hallucinating its backtest").
- `docs/walkthrough.md`: ten minutes from a strategy you found to a number you measured.
- `chronicle/2026-10-12-reverse-engineer/`: the recorded production run (GIF, transcripts).
