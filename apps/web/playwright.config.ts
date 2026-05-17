import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:5174",
  },
  webServer: [
    {
      command:
        "powershell -NoProfile -Command \"Set-Location ..\\..; python tools\\runtime\\e2e_api_server.py --host 127.0.0.1 --port 8000\"",
      reuseExistingServer: true,
      timeout: 120_000,
      url: "http://127.0.0.1:8000/doc-types",
    },
    {
      command: "npm run dev -- --port 5174 --strictPort",
      reuseExistingServer: true,
      timeout: 120_000,
      url: "http://127.0.0.1:5174",
    },
  ],
});
