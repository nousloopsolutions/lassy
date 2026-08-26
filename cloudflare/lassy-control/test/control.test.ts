import { exports } from "cloudflare:workers";
import { describe, expect, it } from "vitest";

const CONTROL_SECRET = "control-test-secret-32-characters-long";
const RUNNER_SECRET = "runner-test-secret-32-characters-long";

describe("LASSY control flow", () => {
  it("queues and signs an allowlisted job", async () => {
    const created = await exports.default.fetch("https://example.test/control/jobs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Lassy-Control-Secret": CONTROL_SECRET,
      },
      body: JSON.stringify({
        kind: "repo_status",
        workspace: "lassy",
        runner_id: "bigg-rigg",
        idempotency_key: "test-job-12345678",
      }),
    });
    expect(created.status).toBe(201);

    const claimed = await exports.default.fetch("https://example.test/runner/claim", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${RUNNER_SECRET}`,
      },
      body: JSON.stringify({ runner_id: "bigg-rigg" }),
    });
    expect(claimed.status).toBe(200);
    const envelope = (await claimed.json()) as Record<string, unknown>;
    expect(envelope.kind).toBe("repo_status");
    expect(envelope.workspace).toBe("lassy");
    expect(envelope.signature).toMatch(/^[0-9a-f]{64}$/);
    expect(envelope).not.toHaveProperty("runner_secret");
  });

  it("denies unauthenticated control requests", async () => {
    const response = await exports.default.fetch("https://example.test/control/jobs");
    expect(response.status).toBe(401);
  });
});
