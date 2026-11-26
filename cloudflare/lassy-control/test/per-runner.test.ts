import { exports } from "cloudflare:workers";
import { describe, expect, it } from "vitest";
import { runnerSecretName, signObject } from "../src/index";

const CONTROL = "control-test-secret-32-characters-long";
const SHARED = "runner-test-secret-32-characters-long";
const LEGION = "legion-own-secret-32-characters-long!!";

async function queue(runner_id: string, key: string) {
  const r = await exports.default.fetch("https://example.test/control/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Lassy-Control-Secret": CONTROL },
    body: JSON.stringify({ kind: "health", runner_id, idempotency_key: key }),
  });
  expect(r.status).toBe(201);
}

function claim(runner_id: string, secret: string) {
  return exports.default.fetch("https://example.test/runner/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${secret}` },
    body: JSON.stringify({ runner_id }),
  });
}

describe("per-runner secrets", () => {
  it("maps ids to binding names without collisions", () => {
    expect(runnerSecretName("bigg-legion")).toBe("LASSY_RUNNER_SECRET__BIGG_LEGION");
    expect(runnerSecretName("bigg_legion")).toBeNull();
    expect(runnerSecretName("Bigg-Legion")).toBeNull();
  });

  it("legion claims with its own secret and gets an envelope signed with it", async () => {
    await queue("bigg-legion", "legion-own-12345678");
    const r = await claim("bigg-legion", LEGION);
    expect(r.status).toBe(200);
    const env = (await r.json()) as Record<string, unknown>;
    const { signature, ...unsigned } = env;
    expect(signature).toBe(await signObject(unsigned, LEGION));
  });

  it("the shared secret no longer works for a runner that has its own", async () => {
    await queue("bigg-legion", "legion-shared-12345678");
    expect((await claim("bigg-legion", SHARED)).status).toBe(401);
  });

  it("legion's secret can't claim another runner's jobs", async () => {
    await queue("bigg-rigg", "rigg-job-12345678");
    expect((await claim("bigg-rigg", LEGION)).status).toBe(401);
    expect((await claim("bigg-rigg", SHARED)).status).toBe(200); // not yet migrated: shared still works
  });

  it("a result signed with the shared secret is refused for legion", async () => {
    const body = { job_id: "job_12345678", runner_id: "bigg-legion", status: "succeeded" };
    const r = await exports.default.fetch("https://example.test/runner/result", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${LEGION}` },
      body: JSON.stringify({ ...body, signature: await signObject(body, SHARED) }),
    });
    expect(r.status).toBe(401);
  });

  it("non-object bodies get a 400, not an exception", async () => {
    for (const path of ["/runner/claim", "/runner/result"]) {
      for (const body of ["null", "[]", "7", "\"x\"", "{bad"]) {
        const r = await exports.default.fetch(`https://example.test${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${LEGION}` },
          body,
        });
        expect(r.status).toBe(400);
      }
    }
  });

  it("non-string runner_id gets a 400 before any secret lookup", async () => {
    for (const rid of ['{"toString":null}', "7", "null", "[]", "true"]) {
      const r = await exports.default.fetch("https://example.test/runner/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: `{"runner_id":${rid}}`,
      });
      expect(r.status).toBe(400);
    }
  });

  it("oversized bodies are refused before parsing, with or without Content-Length", async () => {
    const big = JSON.stringify({ runner_id: "bigg-legion", pad: "x".repeat(70_000) });
    const r = await exports.default.fetch("https://example.test/runner/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: big,
    });
    expect(r.status).toBe(413);
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(new TextEncoder().encode(big));
        c.close();
      },
    });
    const s = await exports.default.fetch("https://example.test/runner/result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: stream,
      duplex: "half",
    } as RequestInit);
    expect(s.status).toBe(413);
  });
});
