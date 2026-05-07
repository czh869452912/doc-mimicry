import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePane } from "../panes/WorkspacePane";

describe("WorkspacePane activation", () => {
  it("does not open folder nodes as files", async () => {
    const onOpenFile = vi.fn();

    render(
      <WorkspacePane
        activeSession={null}
        activeTask={null}
        docTypes={[]}
        error={null}
        loading={false}
        nodes={[
          {
            id: "task:task-1",
            kind: "task",
            name: "Task",
            taskId: "task-1",
            children: [
              {
                id: "folder:task-1:draft",
                kind: "folder",
                name: "draft/",
                path: "draft",
                taskId: "task-1",
              },
            ],
          },
        ]}
        sessions={[]}
        onCreateWorkspace={vi.fn()}
        onCreateSession={vi.fn()}
        onOpenFile={onOpenFile}
        onSelectSession={vi.fn()}
        onSelectTask={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByText("draft/"));

    expect(onOpenFile).not.toHaveBeenCalled();
  });
});
