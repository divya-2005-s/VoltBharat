import type { UseQueryResult } from '@tanstack/react-query'
import { AlertTriangle, Inbox, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/primitives'
import { ApiError } from '@/lib/api'

export function LoadingBlock({ height = 280, label = 'Loading' }: { height?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-2">
      <Skeleton className="w-full" style={{ height }} />
      <span className="sr-only">{label}…</span>
    </div>
  )
}

export function ErrorState({ error, onRetry, compact }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const msg = error instanceof ApiError ? error.message : 'Something went wrong while loading this data.'
  const unavailable = error instanceof ApiError && (error.status === 503 || error.status === 0)
  return (
    <div role="alert" className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border text-center ${compact ? 'p-4' : 'p-8'}`}>
      <AlertTriangle className="size-5 text-warn" />
      <p className="text-sm font-medium text-ink">{unavailable ? 'Data unavailable' : 'Could not load data'}</p>
      <p className="max-w-md text-xs text-ink-3">{msg} No figures are shown rather than showing estimates.</p>
      {onRetry && (
        <Button size="sm" onClick={onRetry} className="mt-1">
          <RotateCw /> Retry
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-border p-8 text-center">
      <Inbox className="size-5 text-ink-3" />
      <p className="text-sm font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-xs text-ink-3">{children}</div>}
    </div>
  )
}

/** Renders loading / error / data for a query. Keeps showing stale data while refetching. */
export function QueryView<T>({ query, children, height, empty }: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
  height?: number
  empty?: (data: T) => boolean
}) {
  if (query.isPending) return <LoadingBlock height={height} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  if (empty?.(query.data)) return <EmptyState title="No data for the selected filters" />
  return (
    <div className={query.isFetching && query.isPlaceholderData ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
      {children(query.data)}
    </div>
  )
}
