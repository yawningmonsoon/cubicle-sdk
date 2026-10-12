// cubicle-sdk (JS) against a local stand-in server: protocol shape, refusals as kinds, the key never printed. No network.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtempSync, statSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile, execFileSync } from "node:child_process";

const KEY = "ck_test_0123456789abcdef";
const DOSSIER = { schema: "strategy-dossier.v1", target: { kind: "rule-text", first: "workflow_read", why: "x" },
  findings: [{ id: "E1", kind: "observation", source: "words", text: 'markets: "NQ"' }, { id: "E2", kind: "unknown", source: "words", text: "nothing was said about stop", needs: "one short question to the trader" }],
  checklist: [{ id: "market", q: "Which market?", status: "answered", by: ["E1"] }, { id: "stop", q: "Where is the stop?", status: "unresolved", by: ["E2"] }],
  counts: { observation: 1, inference: 0, unknown: 1, answered: 1, partial: 0, unresolved: 1 }, max_claim: "hypothesis", next: ["missing"], say: "x" };
const seen = []; let moves = 0; let srv, url, home;

before(async () => {
  srv = createServer((req, res) => {
    let raw = ""; req.on("data", (c) => (raw += c)); req.on("end", () => {
      const body = JSON.parse(raw || "{}"); seen.push({ path: req.url, auth: req.headers.authorization, ua: req.headers["user-agent"], cookie: req.headers.cookie, body });
      const send = (status, obj, extra = {}) => { res.writeHead(status, { "content-type": "application/json", ...extra }); res.end(JSON.stringify(obj)); };
      const ok = (result) => send(200, { jsonrpc: "2.0", id: body.id, result });
      const tool = (obj, isError = false) => ok({ content: [{ type: "text", text: JSON.stringify(obj) }], ...(isError ? { isError: true } : {}) });
      if (req.url.endsWith("/api/join")) return body.name === "taken" ? send(409, { ok: false, error: "that name is taken" })
        : send(201, { ok: true, name: body.name, agent_id: "0xabc", api_key: KEY, ...(body.code === "JURY-OK" ? { code: { ok: true, agent_turns_per_day: 60, until: "2026-12-06" } } : {}) });
      if (req.url.endsWith("/api/login")) return body.key === KEY ? send(200, { ok: true }, { "set-cookie": "deck_session=s1; Path=/; HttpOnly" }) : send(401, { ok: false, error: "refused" });
      if (req.url.endsWith("/api/jury")) return !(req.headers.cookie ?? "").includes("deck_session=s1") ? send(401, { ok: false, error: "sign in first" })
        : body.code === "JURY-OK" ? send(200, { ok: true, agent_turns_per_day: 60, until: "2026-12-06" }) : send(404, { ok: false, error: "that code is not known" });
      if (body.method === "tools/list") return ok({ tools: [{ name: "reverse", description: "Reverse-engineer what the trader POSTED. More." }] });
      if (body.method === "tools/call") {
        if (req.headers.authorization !== `Bearer ${KEY}`) return send(200, { jsonrpc: "2.0", id: body.id, error: { code: -32001, message: "unauthenticated: sign in", data: { next: { step: "key" } } } });
        const { name, arguments: args } = body.params;
        if (name === "reverse") return tool(DOSSIER);
        if (name === "workflow_read") return tool({ ready: !/incomplete/.test(args.text), missing: /incomplete/.test(args.text) ? ["the trigger"] : [], parts: [] });
        if (name === "studio_move") { if (args.move !== "reset") moves++; return tool({ studio_state: "X" }); }
        if (name === "forge") return moves >= 2 ? tool({ seed_hash: "a".repeat(64), studio_state: "REHEARSED" })
          : tool({ refused: true, status: 409, say_to_trader: "the studio is waiting", studio_state: "CLARIFIED",
              mcp_move: moves === 0 ? { tool: "studio_move", arguments: { move: "score_parts" }, without_jev: { tool: "studio_move", arguments: { move: "accept_parts" } } } : { tool: "studio_move", arguments: { move: "choose_coverage", choice: "approximate" } } }, true);
        if (name === "rehearse") return tool({ rehearsal: { receipts: 5, hours: 168, sumR: 2.5, pValue: null, unresolved: [] }, gate: "5 trades in a week. At least 10 are needed to judge it.", means: "past bars, not a forecast" });
        return send(200, { jsonrpc: "2.0", id: body.id, error: { code: -32601, message: "no such tool" } });
      }
      ok({ protocolVersion: "2025-06-18", serverInfo: { name: "cubicle", version: "1.1.0" } });
    });
  });
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  url = `http://127.0.0.1:${srv.address().port}/deck/api/mcp`;
  home = mkdtempSync(join(tmpdir(), "cubicle-sdk-"));
  process.env.HOME = home; process.env.USERPROFILE = home; delete process.env.CUBICLE_KEY;
});
after(() => srv.close());
const sdk = () => import("./index.mjs");

test("tools need no key and the client names itself", async () => {
  const { Cubicle } = await sdk();
  assert.deepEqual((await new Cubicle({ key: "", url }).tools()).map((t) => t.name), ["reverse"]);
  assert.equal(seen.at(-1).auth, undefined); assert.match(seen.at(-1).ua, /^cubicle-sdk-js\//);
});

test("a call without a key is a kind with the server's next step", async () => {
  const { Cubicle, CubicleError } = await sdk();
  await assert.rejects(new Cubicle({ key: "", url }).call("reverse", { text: "x" }), (e) => e instanceof CubicleError && e.kind === "unauthenticated" && e.next.step === "key");
});

test("reverse returns the dossier and renders it in full; an unknown tool is an error", async () => {
  const { Cubicle, render } = await sdk();
  const c = new Cubicle({ key: KEY, url });
  const text = render(await c.reverse("buy NQ"));
  assert.match(text, /1 observed · 0 inferred · 1 unknown/); assert.match(text, /\[x\] Which market\?/); assert.match(text, /settles it: one short question to the trader/);
  await assert.rejects(c.call("nope", { name: "x" }), (e) => e.kind === "unknown_tool");
});

test("reconstruct follows the studio's own moves only when accept is given, and never scores with Jev for the caller", async () => {
  const { Cubicle } = await sdk();
  const c = new Cubicle({ key: KEY, url });
  moves = 0;
  const held = await c.reconstruct("a rule", { market: "NQ" });
  assert.equal(held.stopped, "the studio is waiting"); assert.equal(held.open_move.arguments.move, "accept_parts"); assert.equal(moves, 0);
  const r = await c.reconstruct("a rule", { market: "NQ", accept: true });
  assert.equal(r.forge.seed_hash.length, 64); assert.equal(r.rehearsal.rehearsal.receipts, 5);
  assert.ok(!seen.some((s) => s.body?.params?.arguments?.move === "score_parts"));
  assert.match((await c.reconstruct("an incomplete rule")).stopped, /missing: the trigger/);
});

test("join saves the key 0600 and never prints it; a code is redeemed at join or later", async () => {
  const { Cubicle, redeem, readKey } = await sdk();
  const c = await Cubicle.join("judge-1", { url, code: "JURY-OK" });
  assert.equal(c.code.agent_turns_per_day, 60);
  const f = join(home, ".cubicle", "key");
  if (process.platform !== "win32") assert.equal(statSync(f).mode & 0o777, 0o600);
  assert.equal(readFileSync(f, "utf8").trim(), KEY); assert.equal(readKey(), KEY);
  assert.ok(!JSON.stringify(c).includes(KEY)); assert.ok(!(await import("node:util")).inspect(c).includes(KEY));
  assert.equal((await redeem("JURY-OK", { url })).until, "2026-12-06");
  await assert.rejects(redeem("JURY-NO", { url }), (e) => e.kind === "unknown_code");
  await assert.rejects(redeem("JURY-OK", { url, key: "not-the-key" }), (e) => e.kind === "unauthenticated");
  await assert.rejects(Cubicle.join("taken", { url }), (e) => e.kind === "name_taken");
});

test("the CLI prints usage, and a refusal as one JSON line on stderr with exit 2", async () => {
  assert.match(execFileSync(process.execPath, ["cli.mjs", "--help"], { encoding: "utf8" }), /^usage: cubicle join/);
  // async: the stand-in server lives in this process, and a synchronous spawn would stop it answering
  const r = await new Promise((done) => execFile(process.execPath, ["cli.mjs", "call", "tape"], { encoding: "utf8", env: { ...process.env, HOME: mkdtempSync(join(tmpdir(), "empty-")), CUBICLE_KEY: "", CUBICLE_URL: url } },
    (err, stdout, stderr) => done({ status: err?.code ?? 0, stdout, stderr })));
  assert.equal(r.status, 2); assert.ok(!r.stdout);
  const e = JSON.parse(r.stderr.trim().split("\n").at(-1)); assert.deepEqual([e.ok, e.error.kind], [false, "unauthenticated"]);
});
