export function Loading({ children }: { children?: React.ReactNode }) {
  if (children) return <>{children}</>;
  return (
    <div className="p-8 text-slate-400" role="status" aria-live="polite">
      Loading…
    </div>
  );
}
