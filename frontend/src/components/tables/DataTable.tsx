import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { formatIN } from '@/lib/formatters'
import { cn } from '@/lib/utils'

export interface Column<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  align?: 'left' | 'right'
  sortable?: boolean
  className?: string
  hideBelow?: 'sm' | 'md' | 'lg'
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  sort?: { key: string; order: 'asc' | 'desc' }
  onSort?: (key: string) => void
  onRowClick?: (row: T) => void
  selectedKey?: string | null
  caption: string
  page?: { page: number; pageSize: number; total: number; onPage: (p: number) => void }
  dense?: boolean
}

const hide = { sm: 'hidden sm:table-cell', md: 'hidden md:table-cell', lg: 'hidden lg:table-cell' }

/** Accessible, sortable, paginated table. Sorting/paging can be server-side (controlled). */
export function DataTable<T>({ columns, rows, rowKey, sort, onSort, onRowClick, selectedKey, caption, page, dense }: Props<T>) {
  const pages = page ? Math.max(1, Math.ceil(page.total / page.pageSize)) : 1
  return (
    <div className="min-w-0">
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-2 text-left text-xs font-medium text-ink-3">
            <tr>
              {columns.map((c) => {
                const active = sort?.key === c.key
                const Icon = !active ? ArrowUpDown : sort!.order === 'asc' ? ArrowUp : ArrowDown
                return (
                  <th
                    key={c.key}
                    scope="col"
                    aria-sort={active ? (sort!.order === 'asc' ? 'ascending' : 'descending') : undefined}
                    className={cn('whitespace-nowrap px-3 py-2 font-medium', c.align === 'right' && 'text-right', c.hideBelow && hide[c.hideBelow], c.className)}
                  >
                    {c.sortable && onSort ? (
                      <button type="button" onClick={() => onSort(c.key)}
                        className={cn('inline-flex items-center gap-1 hover:text-ink', active && 'text-ink', c.align === 'right' && 'flex-row-reverse')}>
                        {c.header}
                        <Icon className="size-3" aria-hidden />
                      </button>
                    ) : c.header}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const k = rowKey(r)
              return (
                <tr
                  key={k}
                  onClick={onRowClick ? () => onRowClick(r) : undefined}
                  onKeyDown={onRowClick ? (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onRowClick(r)) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cn('border-t border-border', onRowClick && 'cursor-pointer hover:bg-surface-2 focus-visible:bg-surface-2',
                    selectedKey === k && 'bg-accent-soft')}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cn('px-3 text-ink', dense ? 'py-1.5' : 'py-2.5', c.align === 'right' && 'tabular text-right',
                      c.hideBelow && hide[c.hideBelow], c.className)}>
                      {c.cell(r)}
                    </td>
                  ))}
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-sm text-ink-3">No matching rows</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {page && page.total > page.pageSize && (
        <div className="mt-3 flex items-center justify-between text-xs text-ink-3">
          <span>
            {formatIN((page.page - 1) * page.pageSize + 1)}–{formatIN(Math.min(page.total, page.page * page.pageSize))} of {formatIN(page.total)}
          </span>
          <div className="flex items-center gap-1">
            <Button size="icon-sm" variant="outline" aria-label="Previous page" disabled={page.page <= 1} onClick={() => page.onPage(page.page - 1)}>
              <ChevronLeft />
            </Button>
            <span className="px-2">Page {page.page} of {pages}</span>
            <Button size="icon-sm" variant="outline" aria-label="Next page" disabled={page.page >= pages} onClick={() => page.onPage(page.page + 1)}>
              <ChevronRight />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
