import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <p className="text-sm font-semibold text-accent-ink">404</p>
      <h1 className="text-2xl font-semibold text-ink">Page not found</h1>
      <p className="text-sm text-ink-3">The page you are looking for does not exist.</p>
      <Button asChild variant="primary"><Link to="/">Back to Overview</Link></Button>
    </div>
  )
}
