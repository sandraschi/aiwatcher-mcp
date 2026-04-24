import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Zap, Rss, AlertTriangle, TrendingUp,
  RefreshCw, FlaskConical, Bell,
} from 'lucide-react'
import { UrgencyBadge } from '../components/UrgencyBadge'
import { formatDistanceToNow } from 'date-fns'

async function fetchStats() {
  const r = await fetch('/api/stats')
  return r.json()
}
async function fetchItems() {
  const r = await fetch('/api/items?hours=24&limit=10')
  return r.json()
}
async function doPoll() {
  const r = await fetch('/api/poll', { method: 'POST' })
  return r.json()
}
async function doDistill() {
  const r = await fetch('/api/distill', { method: 'POST' })
  return r.json()
}
async function doCheckAlerts() {
  const r = await fetch('/api/alerts/check', { method: 'POST' })
  return r.json()
}

const STAT_CARDS = [
  { key: 'active_feeds',    label: 'Active Feeds',  color: '#3b82f6', icon: Rss },
  { key: 'items_last_24h',  label: 'New Today',     color: '#22c55e', icon: TrendingUp },
  { key: 'unread_items',    label: 'Unread',        color: '#f59e0b', icon: Zap },
  { key: 'critical_items',  label: 'Critical',      color: '#ef4444', icon: AlertTriangle },
]

export function Dashboard() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: fetchStats, refetchInterval: 30_000 })
  const { data: feed } = useQuery({ queryKey: ['items-dash'], queryFn: fetchItems, refetchInterval: 60_000 })
  const poll = useMutation({ mutationFn: doPoll, onSuccess: () => qc.invalidateQueries() })
  const distill = useMutation({ mutationFn: doDistill, onSuccess: () => qc.invalidateQueries() })
  const alerts = useMutation({ mutationFn: doCheckAlerts })

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
            AI Intelligence Dashboard
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Sandra's personal feed distillery
          </p>
        </div>
        <div className="flex gap-2">
          <ActionButton
            icon={<RefreshCw className="w-4 h-4" />}
            label="Poll Feeds"
            loading={poll.isPending}
            onClick={() => poll.mutate()}
          />
          <ActionButton
            icon={<FlaskConical className="w-4 h-4" />}
            label="Distill"
            loading={distill.isPending}
            onClick={() => distill.mutate()}
          />
          <ActionButton
            icon={<Bell className="w-4 h-4" />}
            label="Check Alerts"
            loading={alerts.isPending}
            onClick={() => alerts.mutate()}
            accent
          />
        </div>
      </div>

      {/* Mutation feedback */}
      {poll.data && (
        <div className="text-sm px-4 py-2 rounded-lg" style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}>
          Poll complete — {poll.data.total_new} new items ingested
        </div>
      )}
      {distill.data && (
        <div className="text-sm px-4 py-2 rounded-lg" style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.2)' }}>
          Distilled {distill.data.items_distilled} items
        </div>
      )}
      {alerts.data && (
        <div className="text-sm px-4 py-2 rounded-lg" style={{
          background: alerts.data.count > 0 ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
          color: alerts.data.count > 0 ? '#ef4444' : '#22c55e',
          border: `1px solid ${alerts.data.count > 0 ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
        }}>
          {alerts.data.count > 0
            ? `ALERT: ${alerts.data.count} critical items — robofang + TTS fired`
            : 'No critical items above threshold'}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map(({ key, label, color, icon: Icon }, i) => (
          <motion.div
            key={key}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="rounded-xl p-4 border"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                   style={{ background: `${color}20`, border: `1px solid ${color}40` }}>
                <Icon className="w-4 h-4" style={{ color }} />
              </div>
            </div>
            <div className="text-2xl font-semibold font-mono" style={{ color: 'var(--text-primary)' }}>
              {stats?.[key] ?? '—'}
            </div>
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{label}</div>
          </motion.div>
        ))}
      </div>

      {/* Recent items */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-5 py-4 border-b flex items-center justify-between"
             style={{ borderColor: 'var(--border)' }}>
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Top Items — Last 24h
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            sorted by urgency
          </span>
        </div>
        <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
          {!feed?.items?.length ? (
            <div className="px-5 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              No items yet — click Poll Feeds
            </div>
          ) : feed.items.map((item: any, i: number) => (
            <ItemRow key={item.id ?? i} item={item} />
          ))}
        </div>
      </div>
    </div>
  )
}

function ItemRow({ item }: { item: any }) {
  const age = item.fetched_at
    ? formatDistanceToNow(new Date(item.fetched_at), { addSuffix: true })
    : '—'

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="px-5 py-3.5 flex items-start gap-4 hover:bg-zinc-800/40 transition-colors"
    >
      <div className="pt-0.5">
        <UrgencyBadge score={item.urgency_score} />
      </div>
      <div className="flex-1 min-w-0">
        <a
          href={item.url ?? '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium hover:underline line-clamp-2"
          style={{ color: 'var(--text-primary)' }}
        >
          {item.title}
        </a>
        {item.distilled_summary && (
          <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
            {item.distilled_summary}
          </p>
        )}
        <div className="flex items-center gap-3 mt-1.5">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {item.feed_name}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>·</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{age}</span>
          {item.relevance_score != null && (
            <>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>·</span>
              <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                R={item.relevance_score?.toFixed(1)}
              </span>
            </>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function ActionButton({
  icon, label, loading, onClick, accent = false,
}: {
  icon: React.ReactNode
  label: string
  loading: boolean
  onClick: () => void
  accent?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all border disabled:opacity-50"
      style={accent
        ? { background: 'rgba(239,68,68,0.15)', color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)' }
        : { background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
    >
      {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : icon}
      {label}
    </button>
  )
}
