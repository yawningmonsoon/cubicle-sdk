/**
 * cubicle-sdk — the Cubicle MCP server from Node, zero dependencies.
 *
 *   import { Cubicle } from "cubicle-sdk";
 *   const c = await Cubicle.join("my-agent");            // once: a free key, saved to ~/.cubicle/key (0600), never printed
 *   const c = new Cubicle();                              // afterwards: CUBICLE_KEY or ~/.cubicle/key
 *   const dossier = await c.reverse(pineSource);          // observed / inferred / unknown, the checklist, the ceiling
 *   const bars = await c.call("tape", { market: "BTC", tf: "1h", from: "2026-10-10T00:00:00Z", to: "2026-10-11T00:00:00Z" });
 *
 * One server carries the product for agents: https://cubicle.algotrada.com/deck/api/mcp (streamable HTTP, JSON-RPC 2.0).
 * Listing its tools needs no key; a call needs a Cubicle key as the bearer. The key is read from the environment or a
 * 0600 file, sent only to the server's own host, and never printed, logged or put in an error by this module.
 */
import { chmodSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join as joinPath } from "node:path";

export const URL_DEFAULT = "https://cubicle.algotrada.com/deck/api/mcp";
/** CUBICLE_URL points the client at another deck (a local one, a test server) */
const defaultUrl = () => process.env.CUBICLE_URL || URL_DEFAULT;
export const PROTOCOL = "2025-06-18";
const AGENT = "cubicle-sdk-js/0.2 (+https://github.com/yawningmonsoon/cubicle-sdk)";
export const keyFile = () => joinPath(homedir(), ".cubicle", "key");

/** A refusal. `kind` is stable (route on it, never on the message); `next` is the server's own next step, when it gave one. */
export class CubicleError extends Error {
  constructor(kind, message, next = null, status = null) { super(message); this.name = "CubicleError"; this.kind = kind; this.next = next; this.status = status; }
}

const kindOf = (code, message) => {
  const low = String(message).toLowerCase();
  if (code === -32001 || low.includes("unauthenticated")) return "unauthenticated";
  if (low.includes("upgrade")) return "plan_required";
  if (code === -32601) return "unknown_tool";
  if (code === -32602) return "bad_arguments";
  return "refused";
};

/** CUBICLE_KEY, else the key file. A key file other users can read is refused rather than used. */
export function readKey(path = keyFile()) {
  const env = (process.env.CUBICLE_KEY ?? "").trim();
  if (env) return env;
  let mode;
  try { mode = statSync(path).mode; } catch { return null; }
  if (process.platform !== "win32" && (mode & 0o077)) throw new CubicleError("key_file_open", `${path} is readable by others; run: chmod 600 ${path}`);
  return readFileSync(path, "utf8").trim() || null;
}
export function saveKey(key, path = keyFile()) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  writeFileSync(path, `${key}\n`, { mode: 0o600 });
  chmodSync(path, 0o600);
  return path;
}

async function post(url, body, headers = {}, timeoutMs = 120_000) {
  let r;
  try {
    r = await fetch(url, { method: "POST", headers: { "content-type": "application/json", accept: "application/json, text/event-stream", "user-agent": AGENT, ...headers }, body: JSON.stringify(body), signal: AbortSignal.timeout(timeoutMs) });
  } catch (e) { throw new CubicleError("unreachable", `the server did not answer: ${e?.cause?.code ?? e?.name ?? "network error"}`); }
  let raw = await r.text();
  if ((r.headers.get("content-type") ?? "").includes("text/event-stream")) {
    const data = raw.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim());
    raw = data.at(-1) ?? "{}";
  }
  try { return { status: r.status, json: JSON.parse(raw), cookie: r.headers.getSetCookie?.() ?? [] }; }
  catch { throw new CubicleError("bad_answer", `HTTP ${r.status}: the answer was not JSON`, null, r.status); }
}

export class Cubicle {
  #key; #id = 0;
  constructor({ key, url = defaultUrl(), timeoutMs = 120_000 } = {}) { this.url = url; this.timeoutMs = timeoutMs; this.#key = key ?? readKey(); }
  get signedIn() { return Boolean(this.#key); }
  toJSON() { return { url: this.url, signedIn: this.signedIn }; }                    // never the key
  [Symbol.for("nodejs.util.inspect.custom")]() { return `Cubicle(url=${this.url}, signedIn=${this.signedIn})`; }

  async rpc(method, params) {
    const { status, json } = await post(this.url, { jsonrpc: "2.0", id: ++this.#id, method, ...(params !== undefined ? { params } : {}) },
      this.#key ? { authorization: `Bearer ${this.#key}` } : {}, this.timeoutMs);
    if (json.error) { const m = String(json.error.message ?? "refused"); throw new CubicleError(kindOf(json.error.code, m), m, json.error.data?.next ?? null, status); }
    return json.result;
  }
  initialize() { return this.rpc("initialize", { protocolVersion: PROTOCOL, capabilities: {}, clientInfo: { name: "cubicle-sdk-js", version: "0.2.0" } }); }
  /** Every tool the server serves, with its description and input schema. No key needed. */
  async tools() { return (await this.rpc("tools/list")).tools; }
  /** Call one tool. Returns its JSON when the tool answered JSON, else its text. A refusal throws CubicleError. */
  async call(name, args = {}) {
    const res = await this.rpc("tools/call", { name, arguments: args });
    const text = (res.content ?? []).filter((c) => c.type === "text").map((c) => c.text ?? "").join("\n");
    let out; try { out = JSON.parse(text); } catch { out = text; }
    if (res.isError) {
      const d = out && typeof out === "object" ? out : {};
      const msg = [d.error, d.say_to_trader].find((x) => typeof x === "string") ?? (typeof out === "string" ? out : JSON.stringify(out));
      throw new CubicleError("studio_state" in d ? "studio_gate" : kindOf(null, msg), msg, d.next ?? d.mcp_move ?? null, d.status ?? null);
    }
    return out;
  }
  /** Reverse-engineer what was posted (a rule in words, a Pine script, a transcript): the dossier. */
  reverse(posted) { return this.call("reverse", { text: posted }); }
  /** The studio's deterministic reader: the seven parts from the rule's own words, and what is missing. */
  read(rule) { return this.call("workflow_read", { text: rule }); }
  account() { return this.call("account"); }

  /**
   * Reconstruct a rule: read → the studio's moves → forge → rehearse on the last week of real bars.
   * `accept` is the caller's to give: it accepts the parts as read and builds from the gates the tape can measure.
   */
  async reconstruct(rule, { market, accept = false } = {}) {
    const dossier = await this.reverse(rule);
    const read = await this.read(rule);
    if (!read.ready) return { dossier, read, stopped: `the rule is missing: ${read.missing.join(", ")}` };
    await this.call("studio_move", { move: "reset" });
    const MAY = new Set(["accept_parts", "choose_coverage"]);
    let forged = null;
    for (let i = 0; i < 6 && !forged; i++) {
      try { forged = await this.call("forge", { intent: rule }); }
      catch (e) {
        if (!(e instanceof CubicleError) || e.kind !== "studio_gate") throw e;
        const alt = e.next?.without_jev; const nx = alt && MAY.has(alt.arguments?.move) ? alt : e.next;
        if (!accept || !nx || nx.tool !== "studio_move" || !MAY.has(nx.arguments?.move)) return { dossier, read, stopped: e.message, open_move: nx ?? null };
        await this.call(nx.tool, nx.arguments);
      }
    }
    if (!forged?.seed_hash) return { dossier, read, stopped: "the forge did not return a machine" };
    const rehearsal = await this.call("rehearse", { seed_hash: forged.seed_hash, ...(market ? { market } : {}) });
    return { dossier, read, forge: forged, rehearsal };
  }

  /** Mint a free key (a few a day per client) and, by default, save it 0600. Optionally redeem a shared code at sign-up. */
  static async join(name, { wallet, code, url = defaultUrl(), save = true } = {}) {
    const base = url.replace(/\/api\/mcp$/, "");
    const { status, json } = await post(`${base}/api/join`, { name, ...(wallet ? { wallet } : {}), ...(code ? { code } : {}) });
    if (!json.ok) throw new CubicleError({ 409: "name_taken", 422: "bad_name", 429: "join_limit" }[status] ?? "join_refused", String(json.error ?? `HTTP ${status}`), null, status);
    const c = new Cubicle({ key: json.api_key, url });
    c.name = json.name; c.agentId = json.agent_id; c.code = json.code ?? null;
    if (save) saveKey(json.api_key);
    return c;
  }
}

/** Redeem a shared code (a jury's, a partner's) for the account the key belongs to: more free turns until its end date. */
export async function redeem(code, { key = readKey(), url = defaultUrl() } = {}) {
  if (!key) throw new CubicleError("unauthenticated", "no key: run `cubicle join <name>` first, or set CUBICLE_KEY");
  const base = url.replace(/\/api\/mcp$/, "");
  const login = await post(`${base}/api/login`, { key });
  if (login.status !== 200) throw new CubicleError("unauthenticated", String(login.json.error ?? `login answered ${login.status}`), null, login.status);
  const cookie = login.cookie.map((c) => c.split(";")[0]).join("; ");
  const { status, json } = await post(`${base}/api/jury`, { code }, { cookie });
  if (!json.ok) throw new CubicleError({ 404: "unknown_code", 409: "code_full", 410: "code_ended", 429: "too_many_tries" }[status] ?? "refused", String(json.error ?? `HTTP ${status}`), null, status);
  return json;
}

/** A dossier as plain text: counts and the checklist first, then every finding (none cut off). */
export function render(d) {
  if (d?.schema !== "strategy-dossier.v1") return JSON.stringify(d, null, 2);
  const mark = { observation: "OBSERVED", inference: "INFERRED", unknown: "UNKNOWN " };
  const tick = { answered: "[x]", partial: "[~]", unresolved: "[ ]" };
  const c = d.counts;
  return [
    `target   ${d.target.kind}  (first tool: ${d.target.first})`,
    `findings ${c.observation} observed · ${c.inference} inferred · ${c.unknown} unknown`,
    `ceiling  ${d.max_claim}`, "", "checklist",
    ...d.checklist.map((i) => `  ${tick[i.status]} ${i.q.padEnd(34)} ${i.by.join(" ")}`),
    "", "findings",
    ...d.findings.map((f) => `  ${f.id.padEnd(4)} ${mark[f.kind]}  ${f.text}${f.needs ? `\n       settles it: ${f.needs}` : ""}`),
  ].join("\n");
}
