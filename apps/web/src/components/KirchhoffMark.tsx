import { cn } from 'cn'

/** The Kirchhoff mark (same drawing as public/kirchhoff.svg): a K whose arms meet at a circuit node. */
export function KirchhoffMark({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn('size-5 shrink-0', className)}>
      <rect width="32" height="32" rx="7" fill="#f4f4f5" />
      <g fill="none" stroke="#0b0d10" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 7v18" />
        <path d="M22.5 7.5 13.5 16l9 8.5" />
      </g>
      <circle cx="13.5" cy="16" r="3" fill="#0ea5e9" />
    </svg>
  )
}
