import { render } from "@testing-library/react";
import type { StartRunConfig } from "@assistant-ui/core";
import type { AppendMessage } from "@assistant-ui/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MessageAttachment } from "../../../types";
import {
  addImportedAttachmentForTask,
  takeImportedAttachmentsForTask,
  useDocAgentAssistantRuntime,
} from "../useDocAgentAssistantRuntime";

const { capturedRuntimeOptions } = vi.hoisted(() => ({
  capturedRuntimeOptions: [] as unknown[],
}));

vi.mock("@assistant-ui/react", async () => {
  const actual = await vi.importActual<typeof import("@assistant-ui/react")>("@assistant-ui/react");
  return {
    ...actual,
    useExternalStoreRuntime: vi.fn((options: unknown) => {
      capturedRuntimeOptions.push(options);
      return { __runtime: true };
    }),
  };
});

function Harness(props: Partial<Parameters<typeof useDocAgentAssistantRuntime>[0]>) {
  useDocAgentAssistantRuntime({
    activeTaskId: "task-1",
    events: [],
    isRunning: true,
    onCancel: vi.fn(),
    onReloadInput: vi.fn(),
    onSubmitInput: vi.fn(),
    ...props,
  });
  return null;
}

function latestOptions() {
  return capturedRuntimeOptions.at(-1) as {
    isDisabled?: boolean;
    isSendDisabled?: boolean;
    onCancel?: () => Promise<void>;
    onNew: (message: AppendMessage) => Promise<void>;
    onReload?: (parentId: string | null, config: StartRunConfig) => Promise<void>;
  };
}

describe("useDocAgentAssistantRuntime", () => {
  beforeEach(() => {
    capturedRuntimeOptions.length = 0;
    vi.clearAllMocks();
  });

  it("wires assistant-ui runtime cancellation to the caller", async () => {
    const onCancel = vi.fn().mockResolvedValue(undefined);

    render(<Harness onCancel={onCancel} />);

    await latestOptions().onCancel?.();

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("forwards assistant-ui reload config to the caller", async () => {
    const onReloadInput = vi.fn().mockResolvedValue(undefined);
    const config: StartRunConfig = {
      parentId: "parent-message",
      sourceId: "source-message",
      runConfig: { custom: { retryReason: "manual" } },
    };

    render(<Harness onReloadInput={onReloadInput} />);

    await latestOptions().onReload?.("parent-message", config);

    expect(onReloadInput).toHaveBeenCalledWith("parent-message", config);
  });

  it("passes disabled and send-disabled state through the assistant-ui runtime adapter", () => {
    render(<Harness isDisabled isSendDisabled />);

    expect(latestOptions().isDisabled).toBe(true);
    expect(latestOptions().isSendDisabled).toBe(true);
  });

  it("takes attachments only for the requested task", () => {
    const taskOneAttachment: MessageAttachment = {
      name: "task-1.md",
      markdown_path: "inputs/task-1.md",
    };
    const taskTwoAttachment: MessageAttachment = {
      name: "task-2.md",
      markdown_path: "inputs/task-2.md",
    };
    const store = addImportedAttachmentForTask(
      addImportedAttachmentForTask({}, "task-1", taskOneAttachment),
      "task-2",
      taskTwoAttachment,
    );

    const result = takeImportedAttachmentsForTask(store, "task-2");

    expect(result.attachments).toEqual([taskTwoAttachment]);
    expect(result.nextStore).toEqual({ "task-1": [taskOneAttachment] });
  });
});
