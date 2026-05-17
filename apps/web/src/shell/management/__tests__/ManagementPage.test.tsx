import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "../../../App";
import { api } from "../../../api";

vi.mock("../../../api", () => ({
  api: {
    listSkillPacks: vi.fn().mockResolvedValue([]),
  },
}));

describe("ManagementPage", () => {
  it("renders the dedicated skill pack management route", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createAppRouter(createMemoryHistory({ initialEntries: ["/management/skill-packs"] }));

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Skill Packs" })).toBeTruthy();
    expect(api.listSkillPacks).toHaveBeenCalled();
  });
});
