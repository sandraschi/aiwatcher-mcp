import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ExternalLink, Filter } from 'lucide-react'
import { UrgencyBadge } from '../components/UrgencyBadge'

async function fetchItems(hours: number) {
  const r = await fetch(`/api/items?hours=${hours}&limit=100`)
  return r.json()
}

type FilterT = 'all' | 'critical' | 'high' | 'unscored'

export function NewsPage() {
  const [hours, setHours] = useState(24)
  const [filter, setFilter] = useState<FilterT>('all')
  const { data, isLoading } = useQuery({
    queryKey: ['items', hours],
    queryFn: () => fetchItems(hours),
    refetchInterval: 60_000,
  })

  const items: any[] = (data?.items ?? []).filter((i: any) => {
    if (filter === 'critical') return (i.urgency_score ?? 0) >= 9
    if (filter === 'high') return (i.urgency_score ?? 0) >= 7
    if (filter === 'unscored') return i.urgency_score == null
    return true
  })

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          News Feed
        </h1>
        <div className="flex items-center gap-3">
          {/* Time filter */}
          <select
            value={hours}
            onChange={e => setHours(Number(e.target.value))}
            className="text-sm rounded-lg px-3 py-2 border outline-none"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
          >
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={72}>Last 3d</option>
            <option value={168}>Last 7d</option>
          </select>
          {/* Urgency filter */}
          <div className="flex items-center gap-1 p-1 rounded-lg border"
               style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            {(['all','critical','high','unscored'] as FilterT[]).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize"
                style={filter === f
                  ? { background: 'rgba(245,158,11,0.15)', color: 'var(--accent-amber)' }
                  : { color: 'var(--text-muted)' }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: 'var(--bg-surface)' }} />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {items.length === 0 && (
            <div className="text-center py-12 text-sm" style={{ color: 'var(--text-muted)' }}>
              No items matching filter
            </div>
          )}
          {items.map((item: any, i: number) => (
            <div
              key={item.id ?? i}
              className="rounded-xl border p-4 hover:border-zinc-600 transition-colors"
              style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
            >
              <div className="flex items-start gap-3">
                <div className="pt-0.5 flex-shrink-0">
                  <UrgencyBadge score={item.urgency_score} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <a
                      href={item.url ?? '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium hover:underline flex-1"
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {item.title}
                    </a>
                    {item.url && (
                      <a href={item.url} target="_blank" rel="noopener noreferrer"
                         style={{ color: 'var(--text-muted)' }} className="flex-shrink-0 mt-0.5">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                  {item.distilled_summary && (
                    <p className="text-xs mt-2 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                      {item.distilled_summary}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-2.5 flex-wrap">
                    <span className="text-xs font-medium" style={{ color: 'var(--accent-amber)' }}>
                      {item.feed_name}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {item.fetched_at
                        ? formatDistanceToNow(new Date(item.fetched_at), { addSuffix: true })
                        : '—'}
                    </span>
                    {item.urgency_score != null && (
                      <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                        U={item.urgency_score?.toFixed(1)} R={item.relevance_score?.toFixed(1)}
                      </span>
                    )}
                    {/* Tags */}
                    {(() => {
                      try {
                        const tags = JSON.parse(item.tags || '[]') as string[]
                        return tags.slice(0, 4).map(t => (
                          <span key={t} className="text-xs px-2 py-0.5 rounded-full"
                                style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.2)' }}>
                            {t}
                          </span>
                        ))
                      } catch { return null }
                    })()}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
