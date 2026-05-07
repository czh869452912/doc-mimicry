import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:5173",
  },
  webServer: [
    {
      command:
        "powershell -NoProfile -Command \"Set-Location ..\\..; $env:DOCAGENT_RUNTIME='mock'; $env:PYTHONPATH='packages\\contracts;packages\\workspace;packages\\timeline;tools\\import;services\\api;agent\\runtime-adapters\\mock;agent\\runtime-adapters\\openhands'; .\\.local\\dev\\.venv\\Scripts\\python.exe -m uvicorn docagent_api.app:app --host 127.0.0.1 --port 8000\"",
      reuseExistingServer: true,
      timeout: 120_000,
      url: "http://127.0.0.1:8000/doc-types",
    },
    {
      command: "npm run dev",
      reuseExistingServer: true,
      timeout: 120_000,
      url: "http://127.0.0.1:5173",
    },
  ],
});
