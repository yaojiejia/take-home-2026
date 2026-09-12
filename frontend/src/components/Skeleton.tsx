export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-neutral-100 ${className}`} aria-hidden="true" />
}
