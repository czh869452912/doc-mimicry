import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DraftEditor } from "../DraftEditor";

interface MockCodeMirrorProps {
  editable?: boolean;
  extensions: unknown[];
  onChange: (
    value: string,
    viewUpdate: {
      state: {
        selection: { main: { from: number; to: number } };
        sliceDoc: (from: number, to: number) => string;
      };
    },
  ) => void;
  value: string;
}

const { codeMirrorProps } = vi.hoisted(() => ({
  codeMirrorProps: [] as unknown[],
}));

function latestCodeMirrorProps() {
  return codeMirrorProps.at(-1) as MockCodeMirrorProps | undefined;
}

vi.mock("@uiw/react-codemirror", () => ({
  default: vi.fn((props: MockCodeMirrorProps) => {
    codeMirrorProps.push(props);
    return (
      <textarea
        data-testid="mock-codemirror"
        readOnly={props.editable === false}
        value={props.value}
        onChange={() => {}}
      />
    );
  }),
}));

function fakeViewUpdate(selectedText: string) {
  return {
    state: {
      selection: { main: { from: 0, to: selectedText.length } },
      sliceDoc: vi.fn(() => selectedText),
    },
  };
}

describe("DraftEditor", () => {
  beforeEach(() => {
    codeMirrorProps.length = 0;
    vi.clearAllMocks();
  });

  it("does not create a new extensions array when props are stable", () => {
    const onChange = vi.fn();
    const onSelection = vi.fn();
    const { rerender } = render(
      <DraftEditor markdown="First draft" onChange={onChange} onSelection={onSelection} />,
    );
    const firstExtensions = latestCodeMirrorProps()?.extensions;

    rerender(<DraftEditor markdown="Second draft" onChange={onChange} onSelection={onSelection} />);

    expect(latestCodeMirrorProps()?.extensions).toBe(firstExtensions);
  });

  it("forwards editor changes and current selected text", () => {
    const onChange = vi.fn();
    const onSelection = vi.fn();
    render(<DraftEditor markdown="First draft" onChange={onChange} onSelection={onSelection} />);

    latestCodeMirrorProps()?.onChange("Updated draft", fakeViewUpdate("selected passage"));

    expect(onChange).toHaveBeenCalledWith("Updated draft");
    expect(onSelection).toHaveBeenCalledWith("selected passage");
  });
});
