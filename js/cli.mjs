#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { Cubicle, CubicleError, redeem, render } from "./index.mjs";

const USAGE = "usage: cubicle join <name> [--code CODE] [--wallet 0x…] | redeem <CODE> | tools | reverse <file|-> [--json] | reconstruct <file> [--market M] [--accept] [--json] | call <tool> [key=value ...]";
const a = process.argv.slice(2);
const flag = (n) => { const i = a.indexOf(n); return i >= 0 && i + 1 < a.length ? a[i + 1] : undefined; };
const coerce = (v) => { try { return JSON.parse(v); } catch { return v; } };
const text = (p) => (p === "-" ? readFileSync(0, "utf8") : readFileSync(p, "utf8"));

try {
  if (!a.length || a[0] === "-h" || a[0] === "--help") console.log(USAGE);
  else if (a[0] === "join" && a[1]) {
    const c = await Cubicle.join(a[1], { code: flag("--code"), wallet: flag("--wallet") });
    console.log(JSON.stringify({ ok: true, name: c.name, agent_id: c.agentId, key_saved_to: "~/.cubicle/key", key_printed: false, ...(c.code ? { code: c.code } : {}) }));
  } else if (a[0] === "redeem" && a[1]) console.log(JSON.stringify(await redeem(a[1])));
  else if (a[0] === "tools") for (const t of await new Cubicle({ key: "" }).tools()) console.log(`${t.name.padEnd(16)} ${(t.description ?? "").split(". ")[0].slice(0, 110)}`);
  else if (a[0] === "reverse" && a[1]) { const d = await new Cubicle().reverse(text(a[1])); console.log(a.includes("--json") ? JSON.stringify(d) : render(d)); }
  else if (a[0] === "reconstruct" && a[1]) {
    const r = await new Cubicle().reconstruct(text(a[1]).trim(), { market: flag("--market"), accept: a.includes("--accept") });
    if (a.includes("--json")) console.log(JSON.stringify(r));
    else {
      console.log(render(r.dossier), "\n");
      if (r.stopped) { console.log(`stopped  ${r.stopped}${r.open_move ? `\nthe open move: ${JSON.stringify(r.open_move)}${a.includes("--accept") ? "" : "  (pass --accept to make it)"}` : ""}`); process.exitCode = 1; }
      else { const h = r.rehearsal?.rehearsal ?? {}; console.log(`forged   ${r.forge.seed_hash.slice(0, 16)}…\nrehearse ${h.receipts} trades in ${h.hours} h of real bars · sum ${h.sumR}R\ngate     ${r.rehearsal.gate}\nmeans    ${r.rehearsal.means}`); }
    }
  } else if (a[0] === "call" && a[1]) {
    const out = await new Cubicle().call(a[1], Object.fromEntries(a.slice(2).map((p) => { const i = p.indexOf("="); return [p.slice(0, i), coerce(p.slice(i + 1))]; })));
    console.log(typeof out === "string" ? out : JSON.stringify(out, null, 2));
  } else { console.error(USAGE); process.exitCode = 2; }
} catch (e) {
  if (!(e instanceof CubicleError)) throw e;
  console.error(JSON.stringify({ ok: false, error: { kind: e.kind, message: e.message, next: e.next } }));
  process.exitCode = 2;
}
