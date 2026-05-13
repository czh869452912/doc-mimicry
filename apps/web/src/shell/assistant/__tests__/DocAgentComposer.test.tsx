import { AssistantRuntimeProvider, useExternalStoreRuntime, type AppendMessage, type ThreadMessage } from "@assistant-ui/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DocAgentComposer } from "../DocAgentComposer";

function ComposerHarness({
  disabled = false,
  draftText,
  isRunning = false,
  onDraftTextApplied,
  onNew = vi.fn(),
}: {
  disabled?: boolean;
  draftText?: string | null;
  isRunning?: boolean;
  onDraftTextApplied?: () => void;
  onNew?: (message: AppendMessage) => Promise<void>;
}) {
  const runtime = useExternalStoreRuntime<ThreadMessage>({
    messages: [],
    onNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <DocAgentComposer
        disabled={disabled}
        draftText={draftText}
        isRunning={isRunning}
        onDraftTextApplied={onDraftTextApplied}
      />
    </AssistantRuntimeProvider>
  );
}

describe("DocAgentComposer", () => {
  it("shows slash command suggestions when the composer starts with slash", async () => {
    render(<ComposerHarness />);

    await userEvent.type(screen.getByLabelText("Message"), "/");

    expect(await screen.findByRole("button", { name: /\/start start outline loop/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\/check run checklist/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\/export export markdown artifact/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\/help show command help/i })).toBeTruthy();
  });

  it("inserts a selected slash command into the composer", async () => {
    render(<ComposerHarness />);

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "/sta");
    await userEvent.click(await screen.findByRole("button", { name: /\/start start outline loop/i }));

    expect((input as HTMLTextAreaElement).value).toBe("/start ");
  });

  it("applies externally queued draft text to the assistant-ui composer", async () => {
    const onDraftTextApplied = vi.fn();

    render(<ComposerHarness draftText="Please review this selected passage" onDraftTextApplied={onDraftTextApplied} />);

    expect(await screen.findByDisplayValue("Please review this selected passage")).toBeTruthy();
    expect(onDraftTextApplied).toHaveBeenCalledOnce();
  });

  it("does not submit on Enter while the agent is running", async () => {
    const onNew = vi.fn();
    render(<ComposerHarness isRunning onNew={onNew} />);

    const input = screen.getByLabelText("Message");
    expect(input.getAttribute("placeholder")).toBe("Agent is working");
    await userEvent.type(input, "Wait here");
    await userEvent.keyboard("{Enter}");

    expect((input as HTMLTextAreaElement).value).toBe("Wait here\n");
    expect(onNew).not.toHaveBeenCalled();
  });

  it("renders an accessible send button with a visible send icon", () => {
    render(<ComposerHarness />);

    const sendButton = screen.getByRole("button", { name: "Send message" });
    expect(sendButton.querySelector("svg")).toBeTruthy();
  });

  it("unlocks the composer when the running state clears", async () => {
    const { rerender } = render(<ComposerHarness isRunning />);

    expect(screen.getByLabelText("Message").getAttribute("placeholder")).toBe("Agent is working");
    expect(screen.getByRole("button", { name: "Stop the running agent" })).toBeTruthy();

    rerender(<ComposerHarness isRunning={false} />);

    const input = screen.getByLabelText("Message") as HTMLTextAreaElement;
    expect(input.disabled).toBe(false);
    expect(input.getAttribute("placeholder")).toBe("Message the agent, or type / for commands");
    await userEvent.type(input, "Continue");
    expect(screen.getByRole("button", { name: "Send message" }).hasAttribute("disabled")).toBe(false);
  });
});
