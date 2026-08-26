declare module "cloudflare:workers" {
  interface ProvidedEnv extends Env {
    LASSY_RUNNER_SECRET: string;
    LASSY_CONTROL_SECRET: string;
  }
}
