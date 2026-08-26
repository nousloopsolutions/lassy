import { describe, expect, it } from "vitest";
import { canonicalJson, signObject, validateCreateJob } from "../src/index";

describe("canonicalJson", () => {
  it("sorts nested object keys", () => {
    expect(canonicalJson({ z: 1, a: { d: 2, b: 3 } })).toBe(
      '{"a":{"b":3,"d":2},"z":1}',
    );
  });

  it("matches the Python runner HMAC contract", async () => {
    const envelope = {
      expires_at: "2026-08-26T20:05:00.123000Z",
      id: "job_12345678",
      issued_at: "2026-08-26T20:00:00.123000Z",
      kind: "health",
      nonce: "1234567890123456",
      prompt: null,
      workspace: null,
    };
    await expect(
      signObject(envelope, "runner-test-secret-32-characters-long"),
    ).resolves.toBe("c29ab8eb36768f855b64f52ddae776ba5b4e4a6b89c9ee26259aaa3ab5540839");
  });
});

describe("validateCreateJob", () => {
  it("accepts an allowlisted repository check", () => {
    expect(
      validateCreateJob({ kind: "repo_test", runner_id: "bigg-rigg", workspace: "lassy" }),
    ).toMatchObject({ kind: "repo_test", runner_id: "bigg-rigg", workspace: "lassy" });
  });

  it("rejects arbitrary command kinds", () => {
    expect(() =>
      validateCreateJob({ kind: "shell", runner_id: "bigg-rigg", workspace: "lassy" }),
    ).toThrow("unsupported_job_kind");
  });

  it("requires review prompt but refuses prompts for fixed jobs", () => {
    expect(() =>
      validateCreateJob({ kind: "opencode_review", runner_id: "bigg-rigg", workspace: "lassy" }),
    ).toThrow("review_prompt_required");
    expect(() =>
      validateCreateJob({
        kind: "repo_status",
        runner_id: "bigg-rigg",
        workspace: "lassy",
        prompt: "run something else",
      }),
    ).toThrow("prompt_not_allowed");
  });
});
