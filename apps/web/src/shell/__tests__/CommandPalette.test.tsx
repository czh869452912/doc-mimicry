import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "../CommandPalette";

describe("CommandPalette", () => {
  beforeEach(() => {
    class ResizeObserverStub {
      disconnect() {}
      observe() {}
      unobserve() {}
    }

    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("closes when Escape is pressed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={vi.fn()} />);

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when typing inside the command input", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Run command..."), "start");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("runs and closes the selected command", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onRunCommand = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={onRunCommand} />);

    await user.click(screen.getByText("/start"));

    expect(onRunCommand).toHaveBeenCalledWith("/start");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
