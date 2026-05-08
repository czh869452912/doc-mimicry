import { expect, test } from "@playwright/test";

test("workbench shell mounts core surfaces", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("DocAgent")).toBeVisible();
  await expect(page.getByText("Workspaces", { exact: true })).toBeVisible();
  await expect(page.locator(".aui-thread")).toBeVisible();
  await expect(page.locator(".aui-composer")).toBeVisible();
  await expect(page.locator(".conversation-stream")).toHaveCount(0);
  await expect(page.getByLabel("Message")).toBeVisible();
  await expect(page.getByRole("tab", { name: /draft/i })).toBeVisible();
});

test("workbench shell exposes workspace creation flow", async ({ page }) => {
  const title = `First loop PRD ${Date.now()}`;

  await page.goto("/");
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await expect(page.getByText("Document type")).toBeVisible();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Write a PRD for the first usable document imitation loop.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();
  await expect(page.getByText(title).first()).toBeVisible();
  await page.getByRole("button", { name: /new session/i }).click();
  await expect(page.getByText(/session-/i).first()).toBeVisible();
  await expect(page.getByText("Workspace files")).toBeVisible();
});

test("assistant-ui center pane sends messages and renders timeline updates", async ({ page }) => {
  await page.goto("/");
  await createDraftReadyWorkspace(page, `Assistant UI PRD ${Date.now()}`);

  await expect(page.locator(".aui-composer")).toBeVisible();
  await page.getByLabel("Message").fill("Revise the launch scope");
  await page.getByLabel("Message").press("Enter");

  await expect(page.locator(".aui-thread")).toContainText("Revise the launch scope");
  await expect(page.getByRole("button", { name: /copy text/i }).first()).toBeVisible();
  await expect(page.locator(".aui-thread")).toContainText(/agent|processed|message|draft|context/i, { timeout: 10_000 });
});

test("assistant-ui composer exposes slash command suggestions", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Message").fill("/");

  await expect(page.getByRole("listbox", { name: "Slash commands" })).toBeVisible();
  await expect(page.getByRole("button", { name: /\/start start outline loop/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /\/export export markdown artifact/i })).toBeVisible();
});

test("URL params deep-link to a task and session on reload", async ({ page }) => {
  const title = `Deep link test ${Date.now()}`;

  await page.goto("/");
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Deep link test workspace.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();

  await expect(page.getByText(title).first()).toBeVisible();

  // After creation, the URL must contain both task and session query parameters.
  await expect.poll(() => new URL(page.url()).searchParams.get("task")).not.toBeNull();
  await expect.poll(() => new URL(page.url()).searchParams.get("session")).not.toBeNull();
  const deepLinkUrl = page.url();
  const taskId = new URL(deepLinkUrl).searchParams.get("task");
  const sessionId = new URL(deepLinkUrl).searchParams.get("session");
  expect(taskId).not.toBeNull();
  expect(sessionId).not.toBeNull();

  // Reload via the deep-link URL — state must be restored
  await page.goto(deepLinkUrl);
  await expect(page.getByText(title).first()).toBeVisible({ timeout: 5_000 });
  expect(new URL(page.url()).searchParams.get("task")).toBe(taskId);
  expect(new URL(page.url()).searchParams.get("session")).toBe(sessionId);
});

async function createDraftReadyWorkspace(page: import("@playwright/test").Page, title: string) {
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Exercise the assistant-ui center pane.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();
  await page.getByLabel("Message").fill("/start");
  await page.getByLabel("Message").press("Enter");
  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await page.getByRole("button", { name: /approve/i }).click();
  await expect(page.locator(".aui-tool-call").filter({ hasText: "Update draft" })).toBeVisible({ timeout: 8_000 });
  await expect(page.getByRole("button", { name: /draft_ready/i })).toBeVisible({ timeout: 8_000 });
}
