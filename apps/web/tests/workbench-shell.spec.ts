import { expect, test } from "@playwright/test";

test("workbench shell smoke placeholder", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
});
