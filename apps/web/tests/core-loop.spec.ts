import { expect, test, type Page } from "@playwright/test";

async function createWorkspace(page: Page): Promise<{ title: string }> {
  const title = `Loop E2E ${Date.now()}`;
  await page.goto("/");

  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();

  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("E2E test workspace for core loop.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();

  // Workspace creation auto-creates a session — wait for the workspace name to appear
  await expect(page.getByText(title).first()).toBeVisible();
  return { title };
}

async function reachDraftReady(page: Page) {
  await createWorkspace(page);
  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");
  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await page.getByRole("button", { name: /approve/i }).click();
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
}

test("start loop produces outline card", async ({ page }) => {
  await createWorkspace(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");

  // Mock adapter is synchronous; events arrive within 1.5s poll interval
  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await expect(page.getByRole("button", { name: /approve/i })).toBeVisible();
});

test("approve outline makes draft content visible", async ({ page }) => {
  await createWorkspace(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");

  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await page.getByRole("button", { name: /approve/i }).click();

  // Mock adapter generates a draft with heading "PRD Draft"
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
});

test("run checklist shows checklist card", async ({ page }) => {
  await reachDraftReady(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/check");
  await composer.press("Enter");

  await expect(page.getByText(/checklist · succeeded/i)).toBeVisible({ timeout: 8_000 });
});

test("export markdown shows artifact card", async ({ page }) => {
  await reachDraftReady(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/export");
  await composer.press("Enter");

  await expect(page.getByText(/artifact · artifacts\/prd-draft\.md/i)).toBeVisible({ timeout: 8_000 });
});
