import { DurableObject } from "cloudflare:workers";
import { timingSafeEqual } from "node:crypto";

const JOB_KINDS = new Set([
  "health",
  "repo_status",
  "repo_test",
  "repo_lint",
  "opencode_review",
]);
const WORKSPACE_RE = /^[a-zA-Z0-9_-]{1,64}$/;
const RUNNER_RE = /^[a-zA-Z0-9_-]{3,64}$/;

type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "rejected"
  | "cancelled";

type JobRow = {
  id: string;
  kind: string;
  workspace: string | null;
  prompt: string | null;
  runner_id: string;
  status: JobStatus;
  created_at: string;
  claimed_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  output: string | null;
  output_truncated: number;
  idempotency_key: string | null;
  attempts: number;
  evidence_sha256: string | null;
  verification_status: string;
};

type Env = {
  JOBS: DurableObjectNamespace<LassyJobQueue>;
  LASSY_RUNNER_SECRET: string;
  LASSY_CONTROL_SECRET: string;
};

export class LassyJobQueue extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.ctx.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        workspace TEXT,
        prompt TEXT,
        runner_id TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        claimed_at TEXT,
        finished_at TEXT,
        exit_code INTEGER,
        output TEXT,
        output_truncated INTEGER NOT NULL DEFAULT 0,
        idempotency_key TEXT UNIQUE,
        attempts INTEGER NOT NULL DEFAULT 0,
        evidence_sha256 TEXT,
        verification_status TEXT NOT NULL DEFAULT 'pending'
      );
      CREATE INDEX IF NOT EXISTS jobs_runner_status_created
        ON jobs(runner_id, status, created_at);
    `);
  }

  async fetch(request: Request): Promise<Response> {
    try {
      const url = new URL(request.url);
      if (request.method === "POST" && url.pathname === "/jobs") {
        return this.create(await readJson(request));
      }
      if (request.method === "GET" && url.pathname === "/jobs") {
        const limit = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 20), 1), 50);
        const rows = this.ctx.storage.sql
          .exec<JobRow>("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", limit)
          .toArray();
        return json({ jobs: rows.map(publicJob) });
      }
      if (request.method === "POST" && url.pathname === "/claim") {
        const body = await readJson(request);
        return this.claim(String(body.runner_id ?? ""));
      }
      if (request.method === "POST" && url.pathname === "/result") {
        return await this.finish(await readJson(request));
      }
      const match = url.pathname.match(/^\/jobs\/([a-zA-Z0-9_-]{8,80})(\/cancel)?$/);
      if (match && request.method === "GET" && !match[2]) return this.get(match[1]);
      if (match && request.method === "POST" && match[2]) return this.cancel(match[1]);
      return json({ error: "not_found" }, 404);
    } catch {
      return json({ error: "invalid_request" }, 400);
    }
  }

  private create(body: Record<string, unknown>): Response {
    const input = validateCreateJob(body);
    if (input.idempotency_key) {
      const existing = this.ctx.storage.sql
        .exec<JobRow>("SELECT * FROM jobs WHERE idempotency_key = ?", input.idempotency_key)
        .toArray()[0];
      if (existing) return json({ job: publicJob(existing), duplicate: true }, 200);
    }
    const id = `job_${crypto.randomUUID().replaceAll("-", "")}`;
    const createdAt = isoMicros(new Date());
    this.ctx.storage.sql.exec(
      `INSERT INTO jobs
       (id, kind, workspace, prompt, runner_id, status, created_at, idempotency_key)
       VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)`,
      id,
      input.kind,
      input.workspace,
      input.prompt,
      input.runner_id,
      createdAt,
      input.idempotency_key,
    );
    return json({ job: { id, status: "queued", created_at: createdAt } }, 201);
  }

  private claim(runnerId: string): Response {
    if (!RUNNER_RE.test(runnerId)) return json({ error: "invalid_runner_id" }, 400);
    let claimed: JobRow | undefined;
    this.ctx.storage.transactionSync(() => {
      const staleBefore = isoMicros(new Date(Date.now() - 15 * 60_000));
      this.ctx.storage.sql.exec(
        `UPDATE jobs SET status = 'queued', claimed_at = NULL
         WHERE runner_id = ? AND status = 'running' AND claimed_at < ? AND attempts < 3`,
        runnerId,
        staleBefore,
      );
      this.ctx.storage.sql.exec(
        `UPDATE jobs SET status = 'failed', finished_at = ?, verification_status = 'failed',
         output = 'Runner did not return a result after three claims.'
         WHERE runner_id = ? AND status = 'running' AND claimed_at < ? AND attempts >= 3`,
        isoMicros(new Date()),
        runnerId,
        staleBefore,
      );
      const candidate = this.ctx.storage.sql
        .exec<JobRow>(
          "SELECT * FROM jobs WHERE runner_id = ? AND status = 'queued' ORDER BY created_at LIMIT 1",
          runnerId,
        )
        .toArray()[0];
      if (!candidate) return;
      const claimedAt = isoMicros(new Date());
      this.ctx.storage.sql.exec(
        `UPDATE jobs SET status = 'running', claimed_at = ?, attempts = attempts + 1
         WHERE id = ? AND status = 'queued'`,
        claimedAt,
        candidate.id,
      );
      claimed = {
        ...candidate,
        status: "running",
        claimed_at: claimedAt,
        attempts: candidate.attempts + 1,
      };
    });
    return claimed ? json(claimed) : new Response(null, { status: 204 });
  }

  private async finish(body: Record<string, unknown>): Promise<Response> {
    const jobId = String(body.job_id ?? "");
    const runnerId = String(body.runner_id ?? "");
    const status = String(body.status ?? "") as JobStatus;
    if (!/^[a-zA-Z0-9_-]{8,80}$/.test(jobId) || !RUNNER_RE.test(runnerId)) {
      return json({ error: "invalid_result" }, 400);
    }
    if (!new Set(["succeeded", "failed", "rejected"]).has(status)) {
      return json({ error: "invalid_result_status" }, 400);
    }
    const existing = this.ctx.storage.sql
      .exec<JobRow>("SELECT * FROM jobs WHERE id = ?", jobId)
      .toArray()[0];
    if (!existing) return json({ error: "job_not_found" }, 404);
    if (existing.runner_id !== runnerId) return json({ error: "runner_mismatch" }, 403);
    if (["succeeded", "failed", "rejected"].includes(existing.status)) {
      return json({ ok: true, duplicate: true });
    }
    if (existing.status !== "running") {
      return json({ error: "job_not_running", status: existing.status }, 409);
    }
    const output = String(body.output ?? "").slice(0, 32_000);
    const exitCode = typeof body.exit_code === "number" ? body.exit_code : null;
    const finishedAt = String(body.finished_at ?? isoMicros(new Date()));
    const evidenceSha256 = await sha256(output);
    const verificationStatus =
      status !== "succeeded"
        ? "failed"
        : existing.kind === "opencode_review"
          ? "result_captured"
          : "mechanically_verified";
    this.ctx.storage.sql.exec(
      `UPDATE jobs SET status = ?, finished_at = ?, exit_code = ?, output = ?,
       output_truncated = ?, evidence_sha256 = ?, verification_status = ? WHERE id = ?`,
      status,
      finishedAt,
      exitCode,
      output,
      body.output_truncated === true ? 1 : 0,
      evidenceSha256,
      verificationStatus,
      jobId,
    );
    return json({ ok: true });
  }

  private get(id: string): Response {
    const row = this.ctx.storage.sql.exec<JobRow>("SELECT * FROM jobs WHERE id = ?", id).toArray()[0];
    return row ? json({ job: publicJob(row) }) : json({ error: "job_not_found" }, 404);
  }

  private cancel(id: string): Response {
    const row = this.ctx.storage.sql.exec<JobRow>("SELECT * FROM jobs WHERE id = ?", id).toArray()[0];
    if (!row) return json({ error: "job_not_found" }, 404);
    if (row.status !== "queued") return json({ error: "job_not_queued" }, 409);
    this.ctx.storage.sql.exec(
      "UPDATE jobs SET status = 'cancelled', finished_at = ? WHERE id = ?",
      isoMicros(new Date()),
      id,
    );
    return json({ ok: true, status: "cancelled" });
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ service: "lassy-control", status: "ok" });
    }
    const queue = env.JOBS.getByName("primary");
    if (url.pathname.startsWith("/runner/")) {
      if (!authorized(request.headers.get("Authorization"), env.LASSY_RUNNER_SECRET, true)) {
        return json({ error: "unauthorized" }, 401);
      }
      if (url.pathname === "/runner/claim" && request.method === "POST") {
        const response = await queue.fetch(new Request("https://internal/claim", request));
        if (response.status === 204) return response;
        const row = (await response.json()) as JobRow;
        const issuedAt = isoMicros(new Date());
        const expiresAt = isoMicros(new Date(Date.now() + 5 * 60_000));
        const envelope = {
          id: row.id,
          kind: row.kind,
          workspace: row.workspace,
          prompt: row.prompt,
          issued_at: issuedAt,
          expires_at: expiresAt,
          nonce: crypto.randomUUID().replaceAll("-", ""),
        };
        return json({
          ...envelope,
          signature: await signObject(envelope, env.LASSY_RUNNER_SECRET),
        });
      }
      if (url.pathname === "/runner/result" && request.method === "POST") {
        const body = await readJson(request);
        const signature = String(body.signature ?? "");
        const unsigned = { ...body };
        delete unsigned.signature;
        if (!(await verifyObject(unsigned, signature, env.LASSY_RUNNER_SECRET))) {
          return json({ error: "invalid_signature" }, 401);
        }
        return queue.fetch(
          new Request("https://internal/result", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
        );
      }
      return json({ error: "not_found" }, 404);
    }
    if (url.pathname.startsWith("/control/")) {
      if (!authorized(request.headers.get("X-Lassy-Control-Secret"), env.LASSY_CONTROL_SECRET)) {
        return json({ error: "unauthorized" }, 401);
      }
      const internalPath = url.pathname.replace(/^\/control/, "") + url.search;
      return queue.fetch(new Request(`https://internal${internalPath}`, request));
    }
    return json({ error: "not_found" }, 404);
  },
} satisfies ExportedHandler<Env>;

export function validateCreateJob(body: Record<string, unknown>) {
  const kind = String(body.kind ?? "");
  const runnerId = String(body.runner_id ?? "");
  const workspace = body.workspace == null ? null : String(body.workspace);
  const prompt = body.prompt == null ? null : String(body.prompt);
  const idempotencyKey = body.idempotency_key == null ? null : String(body.idempotency_key);
  if (!JOB_KINDS.has(kind)) throw new Error("unsupported_job_kind");
  if (!RUNNER_RE.test(runnerId)) throw new Error("invalid_runner_id");
  if (kind !== "health" && (!workspace || !WORKSPACE_RE.test(workspace))) {
    throw new Error("registered_workspace_required");
  }
  if (kind === "health" && workspace !== null) throw new Error("health_has_no_workspace");
  if (kind === "opencode_review" && (!prompt || prompt.length > 4000)) {
    throw new Error("review_prompt_required");
  }
  if (kind !== "opencode_review" && prompt !== null) throw new Error("prompt_not_allowed");
  if (idempotencyKey !== null && !/^[a-zA-Z0-9_-]{8,80}$/.test(idempotencyKey)) {
    throw new Error("invalid_idempotency_key");
  }
  return {
    kind,
    runner_id: runnerId,
    workspace,
    prompt,
    idempotency_key: idempotencyKey,
  };
}

export function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export async function signObject(value: unknown, secret: string): Promise<string> {
  if (secret.length < 32) throw new Error("runner secret is too short");
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(canonicalJson(value)),
  );
  return [...new Uint8Array(signature)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function verifyObject(value: unknown, signature: string, secret: string): Promise<boolean> {
  if (!/^[0-9a-f]{64}$/.test(signature)) return false;
  const expected = await signObject(value, secret);
  return authorized(signature, expected);
}

function authorized(value: string | null, expected: string, bearer = false): boolean {
  const supplied = bearer && value?.startsWith("Bearer ") ? value.slice(7) : value;
  if (!supplied) return false;
  const left = new TextEncoder().encode(supplied);
  const right = new TextEncoder().encode(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

function publicJob(row: JobRow) {
  return {
    id: row.id,
    kind: row.kind,
    workspace: row.workspace,
    runner_id: row.runner_id,
    status: row.status,
    created_at: row.created_at,
    claimed_at: row.claimed_at,
    finished_at: row.finished_at,
    exit_code: row.exit_code,
    output: row.output,
    output_truncated: row.output_truncated === 1,
    attempts: row.attempts,
    evidence_sha256: row.evidence_sha256,
    verification_status: row.verification_status,
  };
}

function isoMicros(date: Date): string {
  return date.toISOString().replace(/\.(\d{3})Z$/, ".$1000Z");
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  const length = Number(request.headers.get("Content-Length") ?? 0);
  if (length > 64_000) throw new Error("request_too_large");
  const text = await request.text();
  if (text.length > 64_000) throw new Error("request_too_large");
  return JSON.parse(text) as Record<string, unknown>;
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function json(body: unknown, status = 200): Response {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Security-Policy": "default-src 'none'",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}
