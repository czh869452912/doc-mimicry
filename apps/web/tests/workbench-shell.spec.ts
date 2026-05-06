import { expect, test } from "@playwright/test";

test("workbench shell mounts core surfaces", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("DocAgent")).toBeVisible();
  await expect(page.getByText("Workspaces", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Message")).toBeVisible();
  await expect(page.getByRole("tab", { name: /draft/i })).toBeVisible();
});

test("workbench shell exposes workspace creation flow", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /create workspace/i }).click();
  await expect(page.getByText("Document type")).toBeVisible();
  await expect(page.getByText("Brief")).toBeVisible();
});
