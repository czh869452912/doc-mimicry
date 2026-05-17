import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "../../../App";
import { api } from "../../../api";

vi.mock("../../../api", () => ({
  api: {
    addSkillPackFileResource: vi.fn(),
    getSkillPackArtifact: vi.fn(),
    listSkillPacks: vi.fn(),
  },
}));

function renderManagementPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter(createMemoryHistory({ initialEntries: ["/management/skill-packs"] }));

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("ManagementPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listSkillPacks).mockResolvedValue([]);
    vi.mocked(api.getSkillPackArtifact).mockRejectedValue(new Error("404"));
  });

  it("renders the dedicated skill pack management route", async () => {
    renderManagementPage();

    expect(await screen.findByRole("heading", { name: "Skill Packs" })).toBeTruthy();
    expect(api.listSkillPacks).toHaveBeenCalled();
  });

  it("uploads a Word material file into a resource group", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listSkillPacks).mockResolvedValue([
      { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
    ]);
    vi.mocked(api.addSkillPackFileResource).mockResolvedValue({
      id: "resource-1",
      pack_id: "memo",
      group: "examples",
      original_filename: "memo.docx",
      source_path: "resources/original/examples/memo.docx",
      markdown_path: "resources/markdown/examples/memo.md",
      conversion_report_path: "resources/reports/examples/memo.conversion.json",
      status: "warning",
      summary: "",
    });

    renderManagementPage();
    await screen.findByText("Memo");
    await user.upload(
      screen.getByLabelText(/upload material file/i),
      new File(["docx"], "memo.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
    );

    await waitFor(() => expect(api.addSkillPackFileResource).toHaveBeenCalledWith("memo", "examples", expect.any(File)));
  });
});
