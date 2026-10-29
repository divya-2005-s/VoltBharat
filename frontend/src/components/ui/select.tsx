import { Check, ChevronDown } from 'lucide-react'
import { Select as S } from 'radix-ui'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface Option {
  value: string
  label: string
  group?: string
}

interface Props {
  value: string
  onChange: (v: string) => void
  options: Option[]
  label: string // accessible name
  placeholder?: string
  className?: string
  icon?: ReactNode
}

// Radix Select forbids empty-string values; '__all' stands in for "no filter".
export const ALL = '__all'

export function Select({ value, onChange, options, label, placeholder, className, icon }: Props) {
  const groups = [...new Set(options.map((o) => o.group ?? ''))]
  return (
    <S.Root value={value} onValueChange={onChange}>
      <S.Trigger
        aria-label={label}
        className={cn(
          'inline-flex h-9 min-w-0 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-sm text-ink hover:bg-surface-2 data-[placeholder]:text-ink-3 cursor-pointer',
          className,
        )}
      >
        {icon}
        <span className="truncate">
          <S.Value placeholder={placeholder} />
        </span>
        <S.Icon className="ml-auto text-ink-3">
          <ChevronDown className="size-4" />
        </S.Icon>
      </S.Trigger>
      <S.Portal>
        <S.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-[min(380px,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-lg border border-border bg-surface shadow-lg"
        >
          <S.Viewport className="p-1">
            {groups.map((g) => (
              <S.Group key={g || 'default'}>
                {g && <S.Label className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-ink-3">{g}</S.Label>}
                {options
                  .filter((o) => (o.group ?? '') === g)
                  .map((o) => (
                    <S.Item
                      key={o.value}
                      value={o.value}
                      className="relative flex cursor-pointer select-none items-center rounded-md py-1.5 pl-7 pr-2 text-sm text-ink outline-none data-[highlighted]:bg-surface-2"
                    >
                      <S.ItemIndicator className="absolute left-2">
                        <Check className="size-3.5 text-accent-ink" />
                      </S.ItemIndicator>
                      <S.ItemText>{o.label}</S.ItemText>
                    </S.Item>
                  ))}
              </S.Group>
            ))}
          </S.Viewport>
        </S.Content>
      </S.Portal>
    </S.Root>
  )
}
