"""cubicle_sdk.mcp — the Cubicle MCP server from Python or a terminal, stdlib only.

One server carries the whole product for agents: https://cubicle.algotrada.com/deck/api/mcp (streamable HTTP, JSON-RPC 2.0).
Listing its tools needs no key. Calling one needs a Cubicle key as the bearer; a free key is minted once by `join`.

    from cubicle_sdk.mcp import Cubicle
    c = Cubicle.join("my-agent")                      # once: mints a free key, saves it to ~/.cubicle/key (0600)
    c = Cubicle()                                     # afterwards: reads CUBICLE_KEY or ~/.cubicle/key
    d = c.reverse(open("strategy.pine").read())       # the dossier: observed / inferred / unknown, the checklist, the ceiling
    c.call("tape", market="BTC", tf="1h", **{"from": "2026-10-10T00:00:00Z", "to": "2026-10-11T00:00:00Z"})

    python -m cubicle_sdk.mcp join my-agent
    python -m cubicle_sdk.mcp tools
    python -m cubicle_sdk.mcp reverse strategy.pine
    python -m cubicle_sdk.mcp call workflow_read text="On NQ 5m, go long when price breaks above the opening range high"

The key is an identity and a login. It is read from the environment or a 0600 file, sent only to the server's own
host as the bearer, and never printed, logged or put in an error by this module.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

URL = "https://cubicle.algotrada.com/deck/api/mcp"
PROTOCOL = "2025-06-18"
KEY_FILE = Path.home() / ".cubicle" / "key"
# python-urllib's default User-Agent is refused at the edge; a client names itself
AGENT = "cubicle-sdk/0.2 (+https://github.com/yawningmonsoon/cubicle-sdk)"


class CubicleError(Exception):
    """A refusal from the server. `kind` is stable (route on it, never on the message); `next` is the server's own
    statement of the step that would lift the refusal (sign in, choose a plan), when it gave one."""

    def __init__(self, kind: str, message: str, next_step: dict | None = None, status: int | None = None):
        super().__init__(message)
        self.kind, self.next, self.status = kind, next_step, status


def _kind(code: int | None, message: str) -> str:
    low = message.lower()
    if code == -32001 or "unauthenticated" in low:
        return "unauthenticated"
    if "upgrade" in low or "plan" in low and "require" in low:
        return "plan_required"
    if code == -32601:
        return "unknown_tool"
    if code == -32602:
        return "bad_arguments"
    return "refused"


def read_key(path: Path | None = None) -> str | None:
    """CUBICLE_KEY, else the key file. A key file other users can read is refused rather than used."""
    path = path or KEY_FILE
    env = os.environ.get("CUBICLE_KEY", "").strip()
    if env:
        return env
    try:
        mode = path.stat().st_mode
    except OSError:
        return None
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise CubicleError("key_file_open", f"{path} is readable by others; run: chmod 600 {path}")
    return path.read_text().strip() or None


def save_key(key: str, path: Path | None = None) -> Path:
    path = path or KEY_FILE
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    os.chmod(path, 0o600)
    return path


class Cubicle:
    def __init__(self, key: str | None = None, url: str | None = None, timeout: float = 120.0):
        self.url, self.timeout = url or os.environ.get("CUBICLE_URL") or URL, timeout
        self._key = key if key is not None else read_key()
        self._id = 0

    def __repr__(self) -> str:  # never the key
        return f"Cubicle(url={self.url!r}, signed_in={bool(self._key)})"

    # ── transport ──────────────────────────────────────────────────────────
    def _post(self, url: str, body: dict, auth: bool = True) -> tuple[int, dict]:
        headers = {"content-type": "application/json", "accept": "application/json, text/event-stream", "user-agent": AGENT}
        if auth and self._key:
            headers["authorization"] = f"Bearer {self._key}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                status, raw, ctype = r.status, r.read().decode("utf-8", "replace"), r.headers.get("content-type", "")
        except urllib.error.HTTPError as e:
            status, raw, ctype = e.code, e.read().decode("utf-8", "replace"), e.headers.get("content-type", "")
        except (urllib.error.URLError, TimeoutError) as e:
            raise CubicleError("unreachable", f"the server did not answer: {getattr(e, 'reason', e)}") from None
        if "text/event-stream" in ctype:  # a streamed answer: the last data line is the result
            data = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            raw = data[-1] if data else "{}"
        try:
            return status, json.loads(raw)
        except ValueError:
            raise CubicleError("bad_answer", f"HTTP {status}: the answer was not JSON", status=status) from None

    def rpc(self, method: str, params: dict | None = None) -> Any:
        self._id += 1
        status, j = self._post(self.url, {"jsonrpc": "2.0", "id": self._id, "method": method, **({"params": params} if params is not None else {})})
        if "error" in j:
            e = j["error"] or {}
            msg = str(e.get("message", "refused"))
            raise CubicleError(_kind(e.get("code"), msg), msg, (e.get("data") or {}).get("next"), status)
        return j.get("result")

    # ── the protocol ───────────────────────────────────────────────────────
    def initialize(self) -> dict:
        return self.rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "cubicle-sdk", "version": "0.2.0"}})

    def tools(self) -> list[dict]:
        """Every tool the server serves, with its description and input schema. No key needed."""
        return self.rpc("tools/list")["tools"]

    def call(self, name: str, /, **arguments: Any) -> Any:
        """Call one tool. Returns its JSON when the tool answered JSON, else its text. A refusal raises CubicleError."""
        res = self.rpc("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        try:
            out: Any = json.loads(text)
        except ValueError:
            out = text
        if res.get("isError"):
            # a studio refusal says what to do instead (say_to_trader) and names the move that is open (mcp_move)
            d = out if isinstance(out, dict) else {}
            msg = next((d[k] for k in ("error", "say_to_trader") if isinstance(d.get(k), str)), None) or (json.dumps(out) if d else str(out))
            raise CubicleError("studio_gate" if "studio_state" in d else _kind(None, msg), msg, d.get("next") or d.get("mcp_move"), d.get("status"))
        return out

    # ── the verbs most callers start with ──────────────────────────────────
    def reverse(self, posted: str) -> dict:
        """Reverse-engineer what was posted (a rule in words, a Pine script, a transcript): the dossier."""
        return self.call("reverse", text=posted)

    def read(self, rule: str) -> dict:
        """The studio's deterministic reader: the seven parts from the trader's own words, and what is missing."""
        return self.call("workflow_read", text=rule)

    def account(self) -> dict:
        return self.call("account")

    def reconstruct(self, rule: str, market: str | None = None, accept: bool = False) -> dict:
        """Reconstruct a rule: read → the studio's moves → forge → rehearse on the last week of real bars.
        `accept` is the caller's to give: it accepts the parts as read and builds from the gates the tape can measure.
        Returns {dossier, read, forge, rehearsal}, or {…, stopped, open_move} when a gate is not the caller's to pass."""
        out: dict = {"dossier": self.reverse(rule), "read": self.read(rule)}
        if not out["read"]["ready"]:
            return {**out, "stopped": f"the rule is missing: {', '.join(out['read']['missing'])}"}
        self.call("studio_move", move="reset")
        may = {"accept_parts", "choose_coverage"}
        forged = None
        for _ in range(6):
            try:
                forged = self.call("forge", intent=rule)
                break
            except CubicleError as e:
                if e.kind != "studio_gate":
                    raise
                nxt = e.next or {}
                alt = nxt.get("without_jev") or {}
                if (alt.get("arguments") or {}).get("move") in may:
                    nxt = alt
                if not accept or nxt.get("tool") != "studio_move" or (nxt.get("arguments") or {}).get("move") not in may:
                    return {**out, "stopped": str(e), "open_move": nxt or None}
                self.call(nxt["tool"], **nxt["arguments"])
        if not forged or not forged.get("seed_hash"):
            return {**out, "stopped": "the forge did not return a machine"}
        out["forge"] = forged
        out["rehearsal"] = self.call("rehearse", seed_hash=forged["seed_hash"], **({"market": market} if market else {}))
        return out

    # ── signing in ─────────────────────────────────────────────────────────
    @classmethod
    def join(cls, name: str, wallet: str | None = None, url: str | None = None, save: bool = True, code: str | None = None) -> "Cubicle":
        """Mint a free key (the server allows a few a day per client) and, by default, save it 0600. The key is shown
        by the server once; this method never prints it."""
        c = cls(key="", url=url)
        base = c.url.rsplit("/api/mcp", 1)[0]
        status, j = c._post(f"{base}/api/join", {"name": name, **({"wallet": wallet} if wallet else {}), **({"code": code} if code else {})}, auth=False)
        if not j.get("ok"):
            raise CubicleError({409: "name_taken", 422: "bad_name", 429: "join_limit"}.get(status, "join_refused"), str(j.get("error", f"HTTP {status}")), status=status)
        c._key = j["api_key"]
        c.name, c.agent_id, c.code = j.get("name"), j.get("agent_id"), j.get("code")
        if save:
            save_key(c._key)
        return c


def redeem(code: str, key: str | None = None, url: str | None = None) -> dict:
    """Redeem a shared code (a jury's, a partner's) for the account the key belongs to: more free turns with the house
    agents until the code's end date. The deck's own route takes a browser session, so this logs in with the key first."""
    import http.cookiejar
    key = key if key is not None else read_key()
    if not key:
        raise CubicleError("unauthenticated", "no key: run `cubicle join <name>` first, or set CUBICLE_KEY")
    base = (url or os.environ.get("CUBICLE_URL") or URL).rsplit("/api/mcp", 1)[0]
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(path: str, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers={"content-type": "application/json", "user-agent": AGENT})
        try:
            with op.open(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}
        except (urllib.error.URLError, TimeoutError) as e:
            raise CubicleError("unreachable", f"the server did not answer: {getattr(e, 'reason', e)}") from None

    status, j = post("/api/login", {"key": key})
    if status != 200:
        raise CubicleError("unauthenticated", str(j.get("error", f"login answered {status}")), status=status)
    status, j = post("/api/jury", {"code": code})
    if not j.get("ok"):
        raise CubicleError({404: "unknown_code", 409: "code_full", 410: "code_ended", 429: "too_many_tries"}.get(status, "refused"), str(j.get("error", f"HTTP {status}")), status=status)
    return j


def render(d: dict) -> str:
    """A dossier as plain text: counts and the checklist first, then every finding (none cut off)."""
    if d.get("schema") != "strategy-dossier.v1":
        return json.dumps(d, indent=2)
    mark = {"observation": "OBSERVED", "inference": "INFERRED", "unknown": "UNKNOWN "}
    tick = {"answered": "[x]", "partial": "[~]", "unresolved": "[ ]"}
    c = d["counts"]
    out = [f"target   {d['target']['kind']}  (first tool: {d['target']['first']})",
           f"findings {c['observation']} observed · {c['inference']} inferred · {c['unknown']} unknown",
           f"ceiling  {d['max_claim']}", "", "checklist"]
    out += [f"  {tick[i['status']]} {i['q']:<34} {' '.join(i['by'])}" for i in d["checklist"]]
    out += ["", "findings"]
    for f in d["findings"]:
        out.append(f"  {f['id']:<4} {mark[f['kind']]}  {f['text']}" + (f"\n       settles it: {f['needs']}" if f.get("needs") else ""))
    return "\n".join(out)


def render_run(r: dict) -> str:
    """A reconstruction as plain text: the dossier, then the build and the rehearsal, or where it stopped."""
    head = render(r["dossier"]) + "\n\n"
    if r.get("stopped"):
        return head + f"stopped  {r['stopped']}" + (f"\nthe open move: {json.dumps(r['open_move'])}" if r.get("open_move") else "")
    h = (r["rehearsal"].get("rehearsal") or {})
    return head + "\n".join([f"forged   {r['forge']['seed_hash'][:16]}…", f"rehearse {h.get('receipts')} trades in {h.get('hours')} h of real bars · sum {h.get('sumR')}R",
                              f"gate     {r['rehearsal'].get('gate')}", f"means    {r['rehearsal'].get('means')}"])


def _short(p: Path) -> str:
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def _coerce(v: str) -> Any:
    try:
        return json.loads(v)
    except ValueError:
        return v


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    usage = "usage: cubicle join <name> [wallet] [--code CODE] | redeem <CODE> | tools | reverse <file|-> [--json] | reconstruct <file> [--market M] [--accept] [--json] | call <tool> [key=value ...]"
    if not a or a[0] in ("-h", "--help"):
        print(usage)
        return 0
    try:
        if a[0] == "join" and len(a) >= 2:
            code = a[a.index("--code") + 1] if "--code" in a and a.index("--code") + 1 < len(a) else None
            rest = [x for i, x in enumerate(a[2:], 2) if x != "--code" and a[i - 1] != "--code"]
            c = Cubicle.join(a[1], rest[0] if rest else None, code=code)
            print(json.dumps({"ok": True, "name": c.name, "agent_id": c.agent_id, "key_saved_to": _short(KEY_FILE), "key_printed": False, **({"code": c.code} if c.code else {})}))
        elif a[0] == "redeem" and len(a) >= 2:
            print(json.dumps(redeem(a[1])))
        elif a[0] == "tools":
            for t in Cubicle(key="").tools():
                print(f"{t['name']:<16} {t.get('description', '').split('. ')[0][:110]}")
        elif a[0] == "reverse" and len(a) >= 2:
            posted = sys.stdin.read() if a[1] == "-" else Path(a[1]).read_text()
            d = Cubicle().reverse(posted)
            print(json.dumps(d) if "--json" in a else render(d))
        elif a[0] == "reconstruct" and len(a) >= 2:
            market = a[a.index("--market") + 1] if "--market" in a and a.index("--market") + 1 < len(a) else None
            r = Cubicle().reconstruct(Path(a[1]).read_text().strip(), market=market, accept="--accept" in a)
            print(json.dumps(r) if "--json" in a else render_run(r) + ("" if "--accept" in a or not r.get("open_move") else "  (pass --accept to make it)"))
            if r.get("stopped"):
                return 1
        elif a[0] == "call" and len(a) >= 2:
            args = dict((k, _coerce(v)) for k, v in (p.split("=", 1) for p in a[2:]))
            out = Cubicle().call(a[1], **args)
            print(out if isinstance(out, str) else json.dumps(out, indent=2))
        else:
            print(usage, file=sys.stderr)
            return 2
    except CubicleError as e:
        print(json.dumps({"ok": False, "error": {"kind": e.kind, "message": str(e), "next": e.next}}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
