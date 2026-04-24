import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Plus, ToggleLeft, ToggleRight, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

async function fetchFeeds() {
  const r = await fetch('/api/feeds')
  return r.json()
}

export function FeedsPage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['feeds'], queryFn: fetchFeeds })
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [adding, setAdding] = useState(false)

  const toggle = useMutation({
    mutationFn: async (id: number) => {
      await fetch(`/api/feeds/${id}/toggle`, { method: 'POST' })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feeds'] }),
  })

  const addFeed = useMutation({
    mutationFn: async () => {
      const r = await fetch('/api/feeds/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, url }),
      })
      return r.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feeds'] })
      setName(''); setUrl(''); setAdding(false)
    },
  })

  const feeds: any[] = data?.feeds ?? []

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Feed Sources
        </h1>
        <button
          onClick={() => setAdding(a => !a)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors"
          style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
        >
          <Plus className="w-4 h-4" />
          Add Feed
        </button>
      </div>

      {adding && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="rounded-xl border p-4 space-y-3"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--accent-amber)' }}
        >
          <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Add new feed</p>
          <div className="grid grid-cols-2 gap-3">
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Feed name"
              className="rounded-lg px-3 py-2 text-sm border outline-none"
              style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', borderColor: 'var(--border)' }}
            />
            <input
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://example.com/feed.xml"
              className="rounded-lg px-3 py-2 text-sm border outline-none"
              style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', borderColor: 'var(--border)' }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => addFeed.mutate()}
              disabled={!name || !url || addFeed.isPending}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              style={{ background: 'rgba(245,158,11,0.15)', color: 'var(--accent-amber)', border: '1px solid rgba(245,158,11,0.3)' }}
            >
              {addFeed.isPending ? 'Adding...' : 'Add'}
            </button>
            <button
              onClick={() => setAdding(false)}
              className="px-4 py-2 rounded-lg text-sm"
              style={{ color: 'var(--text-muted)' }}
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        {feeds.map((feed: any) => (
          <div
            key={feed.id}
            className="flex items-center gap-4 px-5 py-4 border-b last:border-b-0 hover:bg-zinc-800/30"
            style={{ borderColor: 'var(--border)' }}
          >
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium" style={{ color: feed.enabled ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {feed.name}
              </div>
              <div className="text-xs mt-0.5 truncate font-mono" style={{ color: 'var(--text-muted)' }}>
                {feed.url}
              </div>
              {feed.last_fetched && (
                <div className="flex items-center gap-1.5 mt-1">
                  <Clock className="w-3 h-3" style={{ color: 'var(--text-muted)' }} />
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {formatDistanceToNow(new Date(feed.last_fetched), { addSuffix: true })}
                  </span>
                </div>
              )}
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full font-mono"
                  style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6', border: '1px solid rgba(59,130,246,0.2)' }}>
              {feed.feed_type}
            </span>
            <button
              onClick={() => toggle.mutate(feed.id)}
              title={feed.enabled ? 'Disable feed' : 'Enable feed'}
              style={{ color: feed.enabled ? 'var(--accent-green)' : 'var(--text-muted)' }}
            >
              {feed.enabled
                ? <ToggleRight className="w-6 h-6" />
                : <ToggleLeft className="w-6 h-6" />}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
