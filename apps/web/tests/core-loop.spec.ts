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
  await sendComposer(page, "/start");
  await expect(outlineCard(page)).toBeVisible({ timeout: 8_000 });
  await outlineCard(page).getByRole("button", { name: /approve/i }).click();
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
  await expect(activeSession(page).filter({ hasText: "draft_ready" })).toBeVisible({ timeout: 8_000 });
}

test("start loop produces outline card", async ({ page }) => {
  await createWorkspace(page);

  await sendComposer(page, "/start");

  // Mock adapter is synchronous; events arrive within 1.5s poll interval
  await expect(outlineCard(page)).toBeVisible({ timeout: 8_000 });
  await expect(outlineCard(page).getByRole("button", { name: /approve/i })).toBeVisible();
  await expect(page.locator(".acp-event").filter({ hasText: /Read .* skill/ }).first()).toBeVisible();
  await expect(page.locator(".acp-event").filter({ hasText: /Analyze .* examples/ }).first()).toBeVisible();
  await expect(page.locator(".acp-event").filter({ hasText: /Build context/ }).first()).toBeVisible();
});

test("approve outline makes draft content visible", async ({ page }) => {
  await createWorkspace(page);

  await sendComposer(page, "/start");

  await expect(outlineCard(page)).toBeVisible({ timeout: 8_000 });
  await outlineCard(page).getByRole("button", { name: /approve/i }).click();

  // Mock adapter generates a draft with heading "PRD Draft"
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
});

test("run checklist shows checklist card", async ({ page }) => {
  await reachDraftReady(page);

  await sendComposer(page, "/check");

  await expect(checklistCard(page)).toBeVisible({ timeout: 8_000 });
});

test("export markdown shows artifact card", async ({ page }) => {
  await reachDraftReady(page);

  await sendComposer(page, "/export");

  await expect(page.getByText(/artifact · artifacts\/prd-draft\.md/i)).toBeVisible({ timeout: 8_000 });
});

test("selected source text can be queued into assistant composer", async ({ page }) => {
  await reachDraftReady(page);

  await page.getByRole("button", { name: "Source" }).click();
  const editor = page.locator(".cm-content");
  await editor.click();
  await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A");

  await expect(page.getByRole("button", { name: "Send to chat" })).toBeVisible({ timeout: 5_000 });
  await page.getByRole("button", { name: "Send to chat" }).click();

  await expect(messageBox(page)).toContainText("Please review this selected passage");
  await expect(messageBox(page)).toContainText("PRD Draft");
});

test("selected source text can trigger revise selection", async ({ page }) => {
  await reachDraftReady(page);

  await page.getByRole("button", { name: "Source" }).click();
  const editor = page.locator(".cm-content");
  await editor.click();
  await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A");

  await expect(page.getByRole("button", { name: "Revise selection" })).toBeVisible({ timeout: 5_000 });
  await page.getByRole("button", { name: "Revise selection" }).click();

  await expect(page.locator(".acp-event").filter({ hasText: "Revise selected passage" }).first()).toBeVisible({ timeout: 8_000 });
});

function messageBox(page: Page) {
  return page.getByRole("textbox", { name: "Message" });
}

async function sendComposer(page: Page, text: string) {
  await messageBox(page).fill(text);
  await page.getByRole("button", { name: /send message/i }).click();
}

function outlineCard(page: Page) {
  return page.locator(".acp-event--card").filter({ hasText: "Outline · waiting for review" }).first();
}

function checklistCard(page: Page) {
  return page.locator(".acp-event--card").filter({ hasText: "Checklist · succeeded" }).first();
}

function activeSession(page: Page) {
  return page.getByRole("button", { name: /session-[a-f0-9]+/i }).first();
}
