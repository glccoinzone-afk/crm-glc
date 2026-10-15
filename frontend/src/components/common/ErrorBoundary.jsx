import React from "react";

export default class ErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("UI crash", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="min-h-screen grid place-items-center p-6 bg-slate-50">
        <div className="max-w-md text-center space-y-3">
          <h1 className="text-lg font-semibold text-slate-900">Something went wrong</h1>
          <p className="text-[13px] text-slate-500">This page hit an unexpected error. Your data is safe — reload to continue.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="h-10 px-4 rounded-lg bg-slate-900 text-white text-[13px]"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
