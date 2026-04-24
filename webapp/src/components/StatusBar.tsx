import { useQuery } from '@tanstack/react-query'
import { Activity, Clock } from 'lucide-react'

async function fetchHealth() {
  const r = await fetch('/api/health')
  return r.json()
}

export function StatusBar() {
  const { data, isError } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 15_000 })
  const ok = !isError && data?.status === 'ok'

  return (
    <header
      className="flex items-center justify-between px-6 py-3 border-b flex-shrink-0"
      style={{ borderColor: 'var(--border)', background: 'var(--bg-secondary)' }}
    >
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
        <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
          AI Intelligence Feed
        </span>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${ok ? 'bg-green-500 animate-pulse-slow' : 'bg-red-500'}`}
          />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {ok ? 'Backend connected' : 'Backend offline'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            {new Date().toLocaleTimeString('de-AT')}
          </span>
        </div>
      </div>
    </header>
  )
}
