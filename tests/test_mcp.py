"""cubicle_sdk.mcp against a local stand-in server: the protocol shape, the refusals as kinds, and the key's handling.
No network: the stand-in speaks the same JSON-RPC the production server does."""
import io
import json
import os
import stat
import threading
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from cubicle_sdk import mcp
from cubicle_sdk.mcp import Cubicle, CubicleError, render

KEY = "ck_test_0123456789abcdef"
DOSSIER = {"schema": "strategy-dossier.v1", "target": {"kind": "rule-text", "first": "workflow_read", "why": "a rule in words"},
           "findings": [{"id": "E1", "kind": "observation", "source": "words", "text": "markets: \"NQ\""},
                        {"id": "E2", "kind": "unknown", "source": "words", "text": "nothing was said about stop", "needs": "one short question to the trader"}],
           "checklist": [{"id": "market", "q": "Which market?", "status": "answered", "by": ["E1"]}, {"id": "stop", "q": "Where is the stop?", "status": "unresolved", "by": ["E2"]}],
           "counts": {"observation": 1, "inference": 0, "unknown": 1, "answered": 1, "partial": 0, "unresolved": 1}, "max_claim": "hypothesis", "next": ["missing"], "say": "x"}
SEEN: list[dict] = []
MOVES: list[str] = []


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        SEEN.append({"path": self.path, "auth": self.headers.get("authorization"), "ua": self.headers.get("user-agent"), "body": body})
        if self.path.endswith("/api/join"):
            if body.get("name") == "taken":
                return self._send(409, {"ok": False, "error": "that name is taken"})
            code = {"code": {"ok": True, "agent_turns_per_day": 60, "until": "2026-12-06"}} if body.get("code") == "JURY-OK" else {}
            return self._send(201, {"ok": True, "name": body["name"], "agent_id": "0xabc", "api_key": KEY, "shown_once": True, **code})
        if self.path.endswith("/api/login"):
            ok = body.get("key") == KEY
            self.send_response(200 if ok else 401); self.send_header("content-type", "application/json")
            if ok: self.send_header("set-cookie", "deck_session=s1; Path=/")
            raw = json.dumps({"ok": ok}).encode(); self.send_header("content-length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if self.path.endswith("/api/jury"):
            if "deck_session=s1" not in (self.headers.get("cookie") or ""):
                return self._send(401, {"ok": False, "error": "sign in first"})
            return self._send(200, {"ok": True, "agent_turns_per_day": 60, "until": "2026-12-06"}) if body.get("code") == "JURY-OK" else self._send(404, {"ok": False, "error": "that code is not known"})
        rid, m = body.get("id"), body.get("method")
        if m == "tools/list":
            return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "reverse", "description": "Reverse-engineer what the trader POSTED. More."}]}})
        if m == "tools/call":
            if self.headers.get("authorization") != f"Bearer {KEY}":
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32001, "message": "unauthenticated: sign in", "data": {"next": {"step": "key"}}}})
            name = body["params"]["name"]
            if name == "reverse":
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(DOSSIER)}]}})
            args = body["params"].get("arguments") or {}
            def tool(obj, err=False):
                return self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": json.dumps(obj)}], **({"isError": True} if err else {})}})
            if name == "workflow_read":
                return tool({"ready": "incomplete" not in args["text"], "missing": ["the trigger"] if "incomplete" in args["text"] else [], "parts": []})
            if name == "studio_move":
                MOVES.append(args["move"])
                return tool({"studio_state": "X"})
            if name == "rehearse":
                return tool({"rehearsal": {"receipts": 5, "hours": 168, "sumR": 2.5, "pValue": None}, "gate": "5 trades in a week. At least 10 are needed to judge it.", "means": "past bars, not a forecast"})
            if name == "forge":
                done = [m for m in MOVES if m in ("accept_parts", "choose_coverage")]
                if args.get("intent") == "a rule" and len(done) >= 2:
                    return tool({"seed_hash": "a" * 64, "studio_state": "REHEARSED"})
                move = {"tool": "studio_move", "arguments": {"move": "score_parts"}, "without_jev": {"tool": "studio_move", "arguments": {"move": "accept_parts"}}} if not done or args.get("intent") != "a rule" else {"tool": "studio_move", "arguments": {"move": "choose_coverage", "choice": "approximate"}}
                return tool({"refused": True, "status": 409, "say_to_trader": "the studio is waiting for accept_parts", "studio_state": "CLARIFIED", "mcp_move": move}, True)
            return self._send(200, {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "no such tool"}})
        self._send(200, {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": mcp.PROTOCOL, "serverInfo": {"name": "cubicle"}}})

    def _send(self, status, obj):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture(scope="module")
def url():
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/deck/api/mcp"
    srv.shutdown()


def test_tools_need_no_key_and_the_client_names_itself(url):
    SEEN.clear()
    assert [t["name"] for t in Cubicle(key="", url=url).tools()] == ["reverse"]
    assert SEEN[-1]["auth"] is None and SEEN[-1]["ua"].startswith("cubicle-sdk/")


def test_a_call_without_a_key_is_a_kind_with_the_servers_next_step(url):
    with pytest.raises(CubicleError) as e:
        Cubicle(key="", url=url).call("reverse", text="x")
    assert e.value.kind == "unauthenticated" and e.value.next == {"step": "key"}


def test_reverse_returns_the_dossier_and_renders_it_in_full(url):
    d = Cubicle(key=KEY, url=url).reverse("buy NQ")
    assert d["counts"]["unknown"] == 1
    text = render(d)
    assert "1 observed · 0 inferred · 1 unknown" in text and "[x] Which market?" in text and "[ ] Where is the stop?" in text
    assert "settles it: one short question to the trader" in text and "ceiling  hypothesis" in text


def test_a_tool_refusal_and_an_unknown_tool_are_errors_not_values(url):
    c = Cubicle(key=KEY, url=url)
    with pytest.raises(CubicleError) as e:
        c.call("forge", intent="x")
    assert "accept_parts" in str(e.value) and e.value.kind == "studio_gate" and e.value.next["tool"] == "studio_move" and e.value.status == 409
    with pytest.raises(CubicleError) as e:
        c.call("nope", name="a tool argument may itself be called name")
    assert e.value.kind == "unknown_tool"


def test_join_saves_the_key_0600_and_never_prints_it(url, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp, "KEY_FILE", tmp_path / ".cubicle" / "key")
    monkeypatch.setattr(mcp, "URL", url)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        assert mcp.main(["join", "my-agent"]) == 0
    assert KEY not in out.getvalue() + err.getvalue() and json.loads(out.getvalue())["key_printed"] is False
    assert stat.S_IMODE(os.stat(mcp.KEY_FILE).st_mode) == 0o600 and Path(mcp.KEY_FILE).read_text().strip() == KEY
    assert KEY not in repr(Cubicle(key=KEY, url=url))
    with redirect_stdout(out), redirect_stderr(err):
        assert mcp.main(["join", "taken"]) == 2
    assert '"kind": "name_taken"' in err.getvalue()


def test_a_key_file_others_can_read_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("CUBICLE_KEY", raising=False)
    p = tmp_path / "key"
    p.write_text(KEY)
    os.chmod(p, 0o644)
    with pytest.raises(CubicleError) as e:
        mcp.read_key(p)
    assert e.value.kind == "key_file_open"
    os.chmod(p, 0o600)
    assert mcp.read_key(p) == KEY
    monkeypatch.setenv("CUBICLE_KEY", "from-env")
    assert mcp.read_key(p) == "from-env"


def test_a_shared_code_is_redeemed_at_join_or_later_by_logging_in_with_the_key(url, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp, "KEY_FILE", tmp_path / ".cubicle" / "key")
    monkeypatch.setattr(mcp, "URL", url)
    out = io.StringIO()
    with redirect_stdout(out):
        assert mcp.main(["join", "judge-1", "--code", "JURY-OK"]) == 0
    j = json.loads(out.getvalue())
    assert j["code"]["agent_turns_per_day"] == 60 and KEY not in out.getvalue()
    assert SEEN[-1]["body"] == {"name": "judge-1", "code": "JURY-OK"}
    assert mcp.redeem("JURY-OK")["until"] == "2026-12-06"
    with pytest.raises(CubicleError) as e:
        mcp.redeem("JURY-NO")
    assert e.value.kind == "unknown_code"
    with pytest.raises(CubicleError) as e:
        mcp.redeem("JURY-OK", key="not-the-key")
    assert e.value.kind == "unauthenticated"


def test_reconstruct_follows_the_studios_moves_only_when_accept_is_given(url):
    c = Cubicle(key=KEY, url=url)
    MOVES.clear()
    held = c.reconstruct("a rule", market="NQ")
    assert held["stopped"].startswith("the studio is waiting") and held["open_move"]["arguments"]["move"] == "accept_parts"
    assert [m for m in MOVES if m != "reset"] == []
    r = c.reconstruct("a rule", market="NQ", accept=True)
    assert len(r["forge"]["seed_hash"]) == 64 and r["rehearsal"]["rehearsal"]["receipts"] == 5
    assert "score_parts" not in MOVES, "a Jev score is never spent for the caller"
    assert "5 trades in 168 h" in mcp.render_run(r)
    assert "missing: the trigger" in c.reconstruct("an incomplete rule")["stopped"]
