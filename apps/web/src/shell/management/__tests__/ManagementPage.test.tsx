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
    addSkillPackTextResource: vi.fn(),
    createSkillCreatorSession: vi.fn(),
    createSkillPack: vi.fn(),
    generateSkillPack: vi.fn(),
    getSkillPackArtifact: vi.fn(),
    getSkillPackResource: vi.fn(),
    listSkillPacks: vi.fn(),
    listSkillPackResources: vi.fn(),
    publishSkillPack: vi.fn(),
    sendSkillCreatorMessage: vi.fn(),
    updateSkillPackArtifact: vi.fn(),
    validateSkillPack: vi.fn(),
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
    vi.mocked(api.listSkillPackResources).mockResolvedValue([]);
    vi.mocked(api.getSkillPackResource).mockRejectedValue(new Error("404"));
    vi.mocked(api.validateSkillPack).mockResolvedValue({ status: "failed", errors: [], warnings: [] });
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

  it("shows an error when material file upload fails", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listSkillPacks).mockResolvedValue([
      { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
    ]);
    vi.mocked(api.addSkillPackFileResource).mockRejectedValue(new Error("413 Payload Too Large"));

    renderManagementPage();
    await screen.findByText("Memo");
    await user.upload(
      screen.getByLabelText(/upload material file/i),
      new File(["too large"], "memo.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByText(/413 Payload Too Large/i)).toBeTruthy();
  });

  it("shows resource conversion warnings and converted markdown", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listSkillPacks).mockResolvedValue([
      { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
    ]);
    vi.mocked(api.listSkillPackResources).mockResolvedValue([
      {
        id: "resource-1",
        pack_id: "memo",
        group: "examples",
        original_filename: "memo.docx",
        source_path: "resources/original/examples/memo.docx",
        markdown_path: "resources/markdown/examples/memo.md",
        conversion_report_path: "resources/reports/examples/memo.conversion.json",
        status: "warning",
        summary: "",
        warnings: [{ type: "docx_format_loss", message: "DOCX layout was reduced.", location: null }],
      },
    ]);
    vi.mocked(api.getSkillPackResource).mockResolvedValue({
      id: "resource-1",
      pack_id: "memo",
      group: "examples",
      original_filename: "memo.docx",
      source_path: "resources/original/examples/memo.docx",
      markdown_path: "resources/markdown/examples/memo.md",
      conversion_report_path: "resources/reports/examples/memo.conversion.json",
      status: "warning",
      summary: "",
      warnings: [{ type: "docx_format_loss", message: "DOCX layout was reduced.", location: null }],
      markdown: "# Converted memo",
      conversion_report: { status: "succeeded_with_warnings" },
    });

    renderManagementPage();
    await screen.findByText("memo.docx");
    expect(screen.getByText("DOCX layout was reduced.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /view converted memo.docx/i }));

    expect(await screen.findByText("# Converted memo")).toBeTruthy();
  });

  it("refreshes the SKILL.md editor after Skill Creator writes artifacts", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listSkillPacks).mockResolvedValue([
      { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
    ]);
    vi.mocked(api.getSkillPackArtifact)
      .mockResolvedValueOnce({ pack_id: "memo", path: "SKILL.md", content: "# Old skill\n" })
      .mockResolvedValueOnce({ pack_id: "memo", path: "SKILL.md", content: "# Generated skill\n" });
    vi.mocked(api.createSkillCreatorSession).mockResolvedValue({
      id: "creator-1",
      pack_id: "memo",
      session_scope: "pack-management",
      status: "idle",
      runtime: null,
      runtime_session_id: null,
    });
    vi.mocked(api.generateSkillPack).mockResolvedValue({ paths: ["SKILL.md"] });

    renderManagementPage();
    expect(await screen.findByDisplayValue(/# Old skill/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: /generate skill/i }));

    await waitFor(() => expect(api.getSkillPackArtifact).toHaveBeenCalledTimes(2));
    expect(await screen.findByDisplayValue(/# Generated skill/)).toBeTruthy();
  });
});
