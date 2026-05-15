import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AcpUiEmbed } from "../AcpUiEmbed";
import { buildAcpUiEmbedUrl } from "../acpUiEmbedUrl";

describe("AcpUiEmbed", () => {
  it("builds an embeddable ACP UI URL with DocAgent session context", () => {
    const url = buildAcpUiEmbedUrl({
      acpUiUrl: "http://127.0.0.1:4173/acp-ui/",
      apiBase: "http://127.0.0.1:8000",
      sessionId: "session-1",
      taskId: "task-1",
      workspaceRoot: "/workspace/state/workspaces/task-1",
    });

    expect(url).toBe(
      "http://127.0.0.1:4173/acp-ui/?docagentSessionId=session-1&docagentTaskId=task-1&docagentApiBase=http%3A%2F%2F127.0.0.1%3A8000&docagentWorkspaceRoot=%2Fworkspace%2Fstate%2Fworkspaces%2Ftask-1&docagentAcpWsUrl=ws%3A%2F%2F127.0.0.1%3A8000%2Fsessions%2Fsession-1%2Facp%2Fws",
    );
  });

  it("preserves a relative API proxy prefix in the embedded ACP WebSocket URL", () => {
    const url = buildAcpUiEmbedUrl({
      acpUiUrl: "http://127.0.0.1:4173/",
      apiBase: "/api",
      sessionId: "session-1",
      taskId: "task-1",
      workspaceRoot: "/workspace/state/workspaces/task-1",
    });

    expect(url).toContain(
      "%2Fapi%2Fsessions%2Fsession-1%2Facp%2Fws",
    );
  });

  it("renders the external ACP client iframe without requiring local timeline events", () => {
    render(
      <AcpUiEmbed
        acpUiUrl="http://127.0.0.1:4173/acp-ui/"
        apiBase="http://127.0.0.1:8000"
        sessionId="session-1"
        taskId="task-1"
        workspaceRoot="/workspace/state/workspaces/task-1"
      />,
    );

    const frame = screen.getByTitle("ACP interaction client") as HTMLIFrameElement;
    expect(frame).toBeTruthy();
    expect(frame.src).toContain("docagentSessionId=session-1");
    expect(frame.src).toContain("docagentAcpWsUrl=");
    expect(frame.src).toContain("docagentWorkspaceRoot=");
  });
});
