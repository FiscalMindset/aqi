import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

/** Error boundary with retry: never a blank screen, never a silent failure. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div role="alert" className="p-4 m-4 rounded bg-red-950/60 border border-red-700">
            <h2 className="font-bold">Something went wrong.</h2>
            <p className="text-sm text-slate-300 mt-1">{this.state.error.message}</p>
            <button
              type="button"
              className="mt-3 px-4 min-h-touch rounded bg-white/10"
              onClick={() => this.setState({ error: null })}
            >
              Try again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
