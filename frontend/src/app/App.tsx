import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'

import { LoadingBlock } from '@/components/dashboard/states'
import { AppShell } from '@/components/layout/AppShell'

const Overview = lazy(() => import('@/pages/Overview'))
const StateExplorer = lazy(() => import('@/pages/StateExplorer'))
const Segments = lazy(() => import('@/pages/Segments'))
const Manufacturers = lazy(() => import('@/pages/Manufacturers'))
const ChargingGap = lazy(() => import('@/pages/ChargingGap'))
const PolicyImpact = lazy(() => import('@/pages/PolicyImpact'))
const Insights = lazy(() => import('@/pages/Insights'))
const DataSources = lazy(() => import('@/pages/DataSources'))
const NotFound = lazy(() => import('@/pages/NotFound'))

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingBlock height={480} label="Loading page" />}>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/states" element={<StateExplorer />} />
          <Route path="/segments" element={<Segments />} />
          <Route path="/manufacturers" element={<Manufacturers />} />
          <Route path="/charging-gap" element={<ChargingGap />} />
          <Route path="/policy" element={<PolicyImpact />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/sources" element={<DataSources />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </AppShell>
  )
}
