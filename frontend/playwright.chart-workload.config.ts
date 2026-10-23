import { defineConfig } from "@playwright/test";

const workloadSeconds = Number(process.env.CHART_WORKLOAD_SECONDS ?? "600");
const warmupSeconds = Number(process.env.CHART_WORKLOAD_WARMUP_SECONDS ?? "60");
const lifecycleCycles = Number(process.env.CHART_WORKLOAD_LIFECYCLE_CYCLES ?? "100");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/chart-workload.workload.ts",
  workers: 1,
  // Match the runner's bounded allowance for lifecycle setup and evidence drain.
  timeout: (workloadSeconds + warmupSeconds + lifecycleCycles * 15 + 300) * 1000,
  use: { baseURL: "http://127.0.0.1:5173", headless: true },
  webServer: {
    command: "npm run dev -- --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    env: {
      ...process.env,
      API_URL: process.env.CHART_WORKLOAD_API_URL ?? "",
      VITE_CHART_ENABLED: "1",
    },
    reuseExistingServer: false,
  },
});
