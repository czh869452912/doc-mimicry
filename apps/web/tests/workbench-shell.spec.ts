import { expect, test } from "@playwright/test";

test("workbench shell mounts core surfaces", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("DocAgent")).toBeVisible();
  await expect(page.getByText("Workspaces", { exact: true })).toBeVisible();
  await expect(page.locator(".acp-thread")).toBeVisible();
  await expect(page.locator(".acp-composer")).toBeVisible();
  await expect(page.locator(".conversation-stream")).toHaveCount(0);
  await expect(messageBox(page)).toBeVisible();
  await expect(page.getByRole("tab", { name: /draft/i })).toBeVisible();
});

test("workbench shell exposes workspace creation flow", async ({ page }) => {
  const title = `First loop workspace ${Date.now()}`;

  await page.goto("/");
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await expect(page.locator("form").getByText("Document type", { exact: true })).toBeVisible();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Write a first usable document imitation loop.");
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

test("ACP center pane sends messages and renders timeline updates", async ({ page }) => {
  await page.goto("/");
  await createDraftReadyWorkspace(page, `Assistant UI workspace ${Date.now()}`);

  await expect(page.locator(".acp-composer")).toBeVisible();
  await sendComposer(page, "Revise the launch scope");

  await expect(page.locator(".acp-thread")).toContainText("Revise the launch scope");
  await expect(page.getByRole("button", { name: /copy text/i }).first()).toBeVisible();
  await expect(page.locator(".acp-thread")).toContainText(/agent|processed|message|draft|context/i, { timeout: 10_000 });
});

test("ACP reload action resends the previous user message", async ({ page }) => {
  await page.goto("/");
  await createDraftReadyWorkspace(page, `Reload workspace ${Date.now()}`);

  await sendComposer(page, "Revise the launch scope");
  await expect(page.locator(".acp-thread")).toContainText("Revise the launch scope");

  const initialCount = await page.locator(".acp-event--user").filter({ hasText: "Revise the launch scope" }).count();
  await page.getByRole("button", { name: /reload response/i }).last().click();

  await expect
    .poll(() => page.locator(".acp-event--user").filter({ hasText: "Revise the launch scope" }).count())
    .toBeGreaterThan(initialCount);
});

test("ACP composer imports text attachments before sending", async ({ page }) => {
  await page.goto("/");
  await createWorkspace(page, `Attachment workspace ${Date.now()}`);

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: /attach file/i }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles({
    name: "scope-notes.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("Attachment context for launch scope."),
  });

  await expect(page.getByText("scope-notes.md")).toBeVisible();
  await sendComposer(page, "Use the attached notes");

  await expect(page.locator(".acp-thread")).toContainText("Attached workspace inputs:", { timeout: 8_000 });
  await expect(page.locator(".acp-thread")).toContainText("- scope-notes.md: inputs/markdown/scope-notes.md");
  await expect(page.getByText("scope-notes.md").first()).toBeVisible();
});

test("ACP composer exposes slash command suggestions", async ({ page }) => {
  await page.goto("/");

  await messageBox(page).fill("/");

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
  await createWorkspace(page, title);
  await sendComposer(page, "/start");
  await expect(outlineCard(page)).toBeVisible({ timeout: 8_000 });
  const approveButton = outlineCard(page).getByRole("button", { name: /approve/i });
  await expect(approveButton).toBeVisible({ timeout: 8_000 });
  await approveButton.evaluate((button) => (button as HTMLButtonElement).click());
  await expect(messageBox(page)).toBeEnabled({ timeout: 8_000 });
  await expect(activeSession(page).filter({ hasText: "draft_ready" })).toBeVisible({ timeout: 8_000 });
}

async function createWorkspace(page: import("@playwright/test").Page, title: string) {
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Exercise the ACP center pane.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();
  await expect(messageBox(page)).toBeEnabled({ timeout: 8_000 });
}

function messageBox(page: import("@playwright/test").Page) {
  return page.getByRole("textbox", { name: "Message" });
}

async function sendComposer(page: import("@playwright/test").Page, text: string) {
  await messageBox(page).fill(text);
  await page.getByRole("button", { name: /send message/i }).click();
}

function outlineCard(page: import("@playwright/test").Page) {
  return page.locator(".acp-event--card").filter({ hasText: "Outline · waiting for review" }).first();
}

function activeSession(page: import("@playwright/test").Page) {
  return page.getByRole("button", { name: /session-[a-f0-9]+/i }).first();
}
