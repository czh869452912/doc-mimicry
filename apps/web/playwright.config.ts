import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:5174",
  },
  webServer: [
    {
      command:
        "powershell -NoProfile -Command \"Set-Location ..\\..; $env:DOCAGENT_RUNTIME='mock'; $env:DOCAGENT_STATE_ROOT='.local\\e2e\\docagent'; $env:PYTHONPATH='packages\\contracts;packages\\conversion;packages\\workspace;packages\\timeline;tools\\import;services\\api;agent\\runtime-adapters\\mock;agent\\runtime-adapters\\openhands'; .\\.local\\dev\\.venv\\Scripts\\python.exe -m uvicorn --factory docagent_api.app:create_app --host 127.0.0.1 --port 8000\"",
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
