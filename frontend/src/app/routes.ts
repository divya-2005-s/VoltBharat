import { BatteryCharging, Car, Database, Factory, Landmark, LayoutDashboard, Lightbulb, Map as MapIcon, type LucideIcon } from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
  dateFilter: boolean
  stateFilter: boolean
}

export const NAV: NavItem[] = [
  { path: '/', label: 'Overview', icon: LayoutDashboard, dateFilter: true, stateFilter: true },
  { path: '/states', label: 'State Explorer', icon: MapIcon, dateFilter: true, stateFilter: false },
  { path: '/segments', label: 'Vehicle Segments', icon: Car, dateFilter: true, stateFilter: true },
  { path: '/manufacturers', label: 'Manufacturers', icon: Factory, dateFilter: true, stateFilter: true },
  { path: '/charging-gap', label: 'Charging Gap', icon: BatteryCharging, dateFilter: true, stateFilter: false },
  { path: '/policy', label: 'Policy Impact', icon: Landmark, dateFilter: true, stateFilter: true },
  { path: '/insights', label: 'Insights', icon: Lightbulb, dateFilter: true, stateFilter: false },
  { path: '/sources', label: 'Data Sources', icon: Database, dateFilter: false, stateFilter: false },
]

export function navFor(pathname: string): NavItem | undefined {
  return NAV.find((n) => (n.path === '/' ? pathname === '/' : pathname.startsWith(n.path)))
}
