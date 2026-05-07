import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error);
    return { hasError: true, message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.label}] unhandled render error`, error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="pane-error" role="alert">
          <p className="pane-note pane-note--error">
            <strong>{this.props.label}</strong> — Something went wrong.
          </p>
          <p className="pane-note body-sm">{this.state.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
