import { ChevronsLeft, ChevronsRight, Menu, Moon, Sun, X, Zap } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { navFor, NAV } from '@/app/routes'
import { DateRangeFilter, StateFilter } from '@/components/filters/Filters'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/overlays'
import { useBootstrap } from '@/hooks/queries'
import { useTheme } from '@/hooks/useTheme'
import { formatDateTime, formatMonth } from '@/lib/formatters'
import { cn } from '@/lib/utils'

function Brand({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent/15 ring-1 ring-accent/30">
        <Zap className="size-4 text-accent" fill="currentColor" />
      </span>
      {!collapsed && (
        <div className="min-w-0 leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-white">VoltBharat</div>
          <div className="truncate text-[11px] text-sidebar-muted">EV Intelligence Platform</div>
        </div>
      )}
    </div>
  )
}

function SidebarNav({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { search } = useLocation()
  // keep global filters (start/end/state) when switching pages; drop page-local params
  const keep = new URLSearchParams(search)
  for (const k of [...keep.keys()]) if (!['start', 'end', 'state'].includes(k)) keep.delete(k)
  const qs = keep.toString() ? `?${keep}` : ''
  return (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map((n) => {
        const link = (
          <NavLink
            key={n.path}
            to={`${n.path}${qs}`}
            end={n.path === '/'}
            onClick={onNavigate}
            className={({ isActive }) => cn(
              'group flex items-center gap-3 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors',
              isActive ? 'bg-sidebar-2 text-white shadow-[inset_2px_0_0_var(--accent)]' : 'text-sidebar-text hover:bg-sidebar-2/60 hover:text-white',
              collapsed && 'justify-center px-0',
            )}
          >
            <n.icon className="size-[18px] shrink-0" aria-hidden />
            {collapsed ? <span className="sr-only">{n.label}</span> : n.label}
          </NavLink>
        )
        return collapsed ? <Tip key={n.path} content={n.label} side="right">{link}</Tip> : link
      })}
    </nav>
  )
}

function Freshness() {
  const { data, isError } = useBootstrap()
  if (isError) return <span className="text-xs text-danger">API offline</span>
  if (!data) return null
  return (
    <Tip content={<>Registrations through <b>{formatMonth(data.meta.data_coverage.end)}</b>. Database last processed {formatDateTime(data.meta.last_processed_at)}.</>}>
      <span className="hidden items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-ink-3 lg:inline-flex" tabIndex={0}>
        <span className="size-1.5 rounded-full bg-accent" aria-hidden />
        Data to {formatMonth(data.meta.data_coverage.end)}
      </span>
    </Tip>
  )
}

function ThemeToggle() {
  const { resolved, toggle } = useTheme()
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label={`Switch to ${resolved === 'dark' ? 'light' : 'dark'} mode`}>
      {resolved === 'dark' ? <Sun /> : <Moon />}
    </Button>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const current = navFor(pathname)
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('vb-sidebar') === 'collapsed'
    } catch {
      return false
    }
  })
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem('vb-sidebar', collapsed ? 'collapsed' : 'open')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      {/* desktop sidebar */}
      <aside className={cn('sticky top-0 hidden h-screen shrink-0 flex-col bg-sidebar px-3 py-4 transition-[width] duration-200 md:flex',
        collapsed ? 'w-[68px]' : 'w-[232px]')}>
        <div className={cn('mb-6 px-1', collapsed && 'flex justify-center px-0')}><Brand collapsed={collapsed} /></div>
        <SidebarNav collapsed={collapsed} />
        <div className="mt-auto">
          {!collapsed && (
            <p className="mb-3 px-2 text-[11px] leading-snug text-sidebar-muted">India's Electric Mobility Intelligence Platform</p>
          )}
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className={cn('flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-xs text-sidebar-muted hover:bg-sidebar-2 hover:text-white', collapsed && 'justify-center')}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronsRight className="size-4" /> : <><ChevronsLeft className="size-4" /> Collapse</>}
          </button>
        </div>
      </aside>

      {/* mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-sidebar px-3 py-4" aria-label="Navigation">
            <div className="mb-6 flex items-center justify-between px-1">
              <Brand />
              <button type="button" className="rounded p-1 text-sidebar-text" onClick={() => setMobileOpen(false)} aria-label="Close menu">
                <X className="size-5" />
              </button>
            </div>
            <SidebarNav collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 sm:px-6">
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu">
              <Menu />
            </Button>
            <nav aria-label="Breadcrumb" className="min-w-0 text-sm">
              <ol className="flex items-center gap-1.5 text-ink-3">
                <li className="hidden sm:block">VoltBharat</li>
                <li className="hidden sm:block" aria-hidden>/</li>
                <li className="truncate font-medium text-ink" aria-current="page">{current?.label ?? 'Not found'}</li>
              </ol>
            </nav>
            <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
              {current?.dateFilter && <DateRangeFilter />}
              {current?.stateFilter && <StateFilter />}
              <Freshness />
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  )
}
