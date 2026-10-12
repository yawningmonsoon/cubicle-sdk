export declare const URL_DEFAULT: string;
export declare const PROTOCOL: string;
export declare function keyFile(): string;
export declare class CubicleError extends Error {
  kind: "unauthenticated" | "plan_required" | "unknown_tool" | "bad_arguments" | "studio_gate" | "refused" | "unreachable" | "bad_answer" | "key_file_open"
    | "name_taken" | "bad_name" | "join_limit" | "join_refused" | "unknown_code" | "code_full" | "code_ended" | "too_many_tries";
  next: Record<string, unknown> | null;
  status: number | null;
  constructor(kind: string, message: string, next?: Record<string, unknown> | null, status?: number | null);
}
export interface Finding { id: string; kind: "observation" | "inference" | "unknown"; source: "image" | "tape" | "script" | "words" | "arithmetic"; text: string; needs?: string }
export interface ChecklistItem { id: string; q: string; status: "answered" | "partial" | "unresolved"; by: string[] }
export interface Dossier {
  schema: "strategy-dossier.v1";
  target: { kind: string; first: string; why: string };
  findings: Finding[];
  checklist: ChecklistItem[];
  counts: { observation: number; inference: number; unknown: number; answered: number; partial: number; unresolved: number };
  max_claim: "anecdote" | "hypothesis";
  next: string[];
  say: string;
}
export interface Tool { name: string; description?: string; inputSchema?: Record<string, unknown> }
export interface Rehearsal { studio_state?: string; rehearsal?: { receipts: number; hours: number; sumR: number | null; pValue: number | null; unresolved: string[] }; gate?: string | null; means?: string }
export interface Reconstruction { dossier: Dossier; read: { ready: boolean; missing: string[]; parts: unknown[] }; forge?: { seed_hash: string; studio_state?: string }; rehearsal?: Rehearsal; stopped?: string; open_move?: unknown }
export interface CodeGrant { ok: boolean; agent_turns_per_day?: number; chat_turns_per_day?: number; until?: string; error?: string; already?: boolean }
export declare class Cubicle {
  url: string; timeoutMs: number; name?: string; agentId?: string; code?: CodeGrant | null;
  readonly signedIn: boolean;
  constructor(options?: { key?: string; url?: string; timeoutMs?: number });
  rpc(method: string, params?: unknown): Promise<any>;
  initialize(): Promise<{ protocolVersion: string; serverInfo: { name: string; version: string } }>;
  tools(): Promise<Tool[]>;
  call<T = any>(name: string, args?: Record<string, unknown>): Promise<T>;
  reverse(posted: string): Promise<Dossier>;
  read(rule: string): Promise<{ ready: boolean; missing: string[]; parts: unknown[] }>;
  account(): Promise<any>;
  reconstruct(rule: string, options?: { market?: string; accept?: boolean }): Promise<Reconstruction>;
  static join(name: string, options?: { wallet?: string; code?: string; url?: string; save?: boolean }): Promise<Cubicle>;
}
export declare function redeem(code: string, options?: { key?: string | null; url?: string }): Promise<CodeGrant>;
export declare function readKey(path?: string): string | null;
export declare function saveKey(key: string, path?: string): string;
export declare function render(d: Dossier | unknown): string;
