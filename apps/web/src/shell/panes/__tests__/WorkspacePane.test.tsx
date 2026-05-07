import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePane } from "../WorkspacePane";

const docTypes = [{ id: "prd", title: "PRD", description: "Product requirements", has_skill: false, resource_groups: {} as Record<string, string[]> }];

const defaultProps = {
  activeSession: null,
  activeTask: null,
  docTypes,
  error: null,
  loading: false,
  nodes: [],
  sessions: [],
  onCreateSession: vi.fn(),
  onCreateWorkspace: vi.fn().mockResolvedValue(undefined),
  onOpenFile: vi.fn(),
  onSelectSession: vi.fn(),
  onSelectTask: vi.fn(),
};

describe("WorkspacePane creation form", () => {
  it("shows validation error when description is empty", async () => {
    const user = userEvent.setup();
    render(<WorkspacePane {...defaultProps} />);

    // Click the header + icon button to open the form (first match)
    const openButtons = screen.getAllByRole("button", { name: /create workspace/i });
    await user.click(openButtons[0]);

    // Form needs aria-label="Create workspace" to be discoverable by role
    const form = screen.getByRole("form", { name: /create workspace/i });
    expect(form).toBeTruthy();

    const descriptionField = screen.getByLabelText("Description");
    await user.clear(descriptionField);

    await user.click(within(form).getByRole("button", { name: /create workspace/i }));

    await waitFor(() => {
      expect(screen.getByText(/description is required/i)).toBeTruthy();
    });

    expect(defaultProps.onCreateWorkspace).not.toHaveBeenCalled();
  });

  it("calls onCreateWorkspace with form values on valid submit", async () => {
    const user = userEvent.setup();
    const onCreateWorkspace = vi.fn().mockResolvedValue(undefined);
    render(<WorkspacePane {...defaultProps} onCreateWorkspace={onCreateWorkspace} />);

    const openButtons = screen.getAllByRole("button", { name: /create workspace/i });
    await user.click(openButtons[0]);

    const form = screen.getByRole("form", { name: /create workspace/i });

    const titleField = screen.getByLabelText("Title");
    await user.clear(titleField);
    await user.type(titleField, "My PRD");

    const descriptionField = screen.getByLabelText("Description");
    await user.clear(descriptionField);
    await user.type(descriptionField, "Build a search feature");

    await user.click(within(form).getByRole("button", { name: /create workspace/i }));

    await waitFor(() => {
      expect(onCreateWorkspace).toHaveBeenCalledWith("prd", {
        title: "My PRD",
        description: "Build a search feature",
      });
    });
  });
});
