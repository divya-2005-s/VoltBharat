// Small shadcn/ui-style primitives: Card, Badge, Skeleton, Input.
import type { HTMLAttributes, InputHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-border bg-surface shadow-[0_1px_2px_rgba(16,24,40,0.04)]', className)} {...p} />
}

export function CardHeader({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-wrap items-start justify-between gap-3 px-5 pt-4', className)} {...p} />
}

export function CardTitle({ className, ...p }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-[15px] font-semibold tracking-tight text-ink', className)} {...p} />
}

export function CardDescription({ className, ...p }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('mt-0.5 text-[13px] text-ink-3', className)} {...p} />
}

export function CardContent({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 pb-5 pt-3', className)} {...p} />
}

type Tone = 'neutral' | 'accent' | 'warn' | 'danger' | 'info'
const tones: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink-2 border-border',
  accent: 'bg-accent-soft text-accent-ink border-transparent',
  warn: 'bg-warn-soft text-warn border-warn-border',
  danger: 'bg-danger-soft text-danger border-transparent',
  info: 'bg-info-soft text-ink-2 border-info-border',
}

export function Badge({ className, tone = 'neutral', ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium [&_svg]:size-3', tones[tone], className)}
      {...p}
    />
  )
}

export function Skeleton({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn('animate-pulse rounded-md bg-surface-2', className)} {...p} />
}

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-9 w-full rounded-md border border-border bg-surface px-3 text-sm text-ink placeholder:text-ink-3 focus-visible:outline-2 focus-visible:outline-accent',
        className,
      )}
      {...p}
    />
  )
}
