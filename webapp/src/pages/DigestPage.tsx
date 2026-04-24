import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { ExternalLink, Send, Eye } from 'lucide-react'

async function fetchDigest(hours: number) {
  const r = await fetch(`/api/digest/preview?hours=${hours}`)
  return r.json()
}

export function DigestPage() {
  const [hours, setHours] = useState(24)
  const [preview, setPreview] = useState(false)
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['digest', hours],
    queryFn: () => fetchDigest(hours),
    enabled: false,
  })

  const send = useMutation({
    mutationFn: async () => {
      const r = await fetch('/api/digest/send', { method: 'POST' })
      return r.json()
    },
  })

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Digest
        </h1>
        <div className="flex items-center gap-3">
          <select
            value={hours}
            onChange={e => setHours(Number(e.target.value))}
            className="text-sm rounded-lg px-3 py-2 border outline-none"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
          >
            <option value={6}>Last 6h</option>
            <option value={24}>Last 24h</option>
            <option value={72}>Last 3d</option>
          </select>
          <button
            onClick={() => { refetch(); setPreview(false) }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
          >
            Generate
          </button>
          <a
            href={`/api/digest/html?hours=${hours}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border"
            style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
          >
            <Eye className="w-4 h-4" />
            Open HTML
          </a>
          <button
            onClick={() => send.mutate()}
            disabled={send.isPending}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border font-medium disabled:opacity-50"
            style={{ background: 'rgba(245,158,11,0.15)', color: 'var(--accent-amber)', borderColor: 'rgba(245,158,11,0.3)' }}
          >
            <Send className="w-4 h-4" />
            {send.isPending ? 'Sending...' : 'Send Now'}
          </button>
        </div>
      </div>

      {send.data && (
        <div className="text-sm px-4 py-2 rounded-lg"
             style={{ background: send.data.sent ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
                      color: send.data.sent ? '#22c55e' : '#ef4444',
                      border: `1px solid ${send.data.sent ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
          {send.data.sent ? 'Digest sent successfully' : 'Send failed — check email config in Settings'}
        </div>
      )}

      {isLoading && (
        <div className="h-64 rounded-xl animate-pulse" style={{ background: 'var(--bg-surface)' }} />
      )}

      {data && (
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Subject</p>
            <p className="text-sm font-medium mt-1" style={{ color: 'var(--text-primary)' }}>
              {data.subject}
            </p>
          </div>
          <div className="px-5 py-4">
            <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>Plain text preview</p>
            <pre className="text-xs leading-relaxed whitespace-pre-wrap font-mono overflow-auto max-h-96"
                 style={{ color: 'var(--text-secondary)' }}>
              {data.text_body}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
