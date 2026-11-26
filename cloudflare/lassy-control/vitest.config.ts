import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          LASSY_RUNNER_SECRET: "runner-test-secret-32-characters-long",
          LASSY_CONTROL_SECRET: "control-test-secret-32-characters-long",
          LASSY_RUNNER_SECRET__BIGG_LEGION: "legion-own-secret-32-characters-long!!",
        },
      },
    }),
  ],
});
