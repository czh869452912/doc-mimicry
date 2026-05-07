import { expect, test } from "@playwright/test";

test("workbench shell mounts core surfaces", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("DocAgent")).toBeVisible();
  await expect(page.getByText("Workspaces", { exact: true })).toBeVisible();
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

test("URL deep-links restore the active task and session", async ({ page }) => {
  const title = `Deep-link PRD ${Date.now()}`;

  await page.goto("/");
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Deep-link restoration test.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();

  await expect(page.getByText(title).first()).toBeVisible();

  // After creation, the URL must contain the task query parameter
  await expect.poll(() => new URL(page.url()).searchParams.get("task")).not.toBeNull();
  const deepLinkUrl = page.url();
  const taskId = new URL(deepLinkUrl).searchParams.get("task");
  expect(taskId).not.toBeNull();

  // Reload via the deep-link URL — state must be restored
  await page.goto(deepLinkUrl);
  await expect(page.getByText(title).first()).toBeVisible();
  expect(new URL(page.url()).searchParams.get("task")).toBe(taskId);
});
