import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const SOURCE_LABELS: Record<string, string> = {
  fuel: 'VAHAN registrations by fuel type',
  maker: 'VAHAN registrations by maker',
  category: 'VAHAN registrations by vehicle category',
  chargers_state: 'Public charging stations by state (2025)',
  chargers_omc: 'OMC charging stations by financial year',
  policy_events: 'Policy milestone reference',
}
