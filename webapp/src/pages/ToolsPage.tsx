import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronRight, Play, Loader2 } from 'lucide-react'

async function fetchCapabilities() {
  const r = await fetch('/api/capabilities')
  return r.json()
}

// Dry-run a tool by calling the appropriate REST endpoint (read-only tools only).
const SAFE_TOOL_ENDPOINTS: Record<string, { method: string; path: string }> = {
  poll_feeds:    { method: 'GET', path: '/api/stats' },   // preview only, not actually polling
  get_top_items: { method: 'GET', path: '/api/items?hours=24&limit=5' },
  get_feeds_list:{ method: 'GET', path: '/api/feeds' },
}

const TOOL_DOCS: Record<string, string> = {
  poll_feeds:      'Poll all enabled RSS/Atom feeds for new items. Manually trigger outside the scheduled 30-minute interval.',
  distill_pending: 'Score unprocessed items with Claude (claude-sonnet-4). Each item gets relevance (0–10), urgency (0–10), a Sandra-voice summary, and tags.',
  check_alerts:    'Find items >= ALERT_THRESHOLD (default 8.5) and fire robofang Council POST + speechops TTS. Falls back to Windows SAPI5.',
  generate_digest: 'Build a full HTML + plain-text digest from scored items in the last N hours.',
  send_digest_now: 'Force-send the digest email to Sandra and Steve outside the 07:00 UTC schedule.',
  get_top_items:   'Return top N items sorted by urgency_score DESC for a given time window.',
  get_feeds_list:  'List all configured feeds with enabled status, type, and last fetch timestamp.',
  add_feed:        'Add a new RSS/Atom source. name + url required; feed_type defaults to "rss".',
  show_dashboard_card: 'Prefab UI — render a stats card in Claude Desktop. Plain-text fallback for other hosts.',
}

export function ToolsPage() {
  const { data: caps } = useQuery({ queryKey: ['capabilities'], queryFn: fetchCapabilities })
  const tools: string[] = caps?.tool_surface?.atomic_tools ?? []
  const [expanded, setExpanded] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, string>>({})

  const run = useMutation({
    mutationFn: async (tool: string) => {
      const endpoint = SAFE_TOOL_ENDPOINTS[tool]
      if (!endpoint) throw new Error('No safe preview endpoint for this tool — use the Dashboard or MCP client.')
      const r = await fetch(endpoint.path, { method: endpoint.method })
      return r.json()
    },
    onSuccess: (data, tool) => {
      setResults((r) => ({ ...r, [tool]: JSON.stringify(data, null, 2) }))
    },
    onError: (err: Error, tool) => {
      setResults((r) => ({ ...r, [tool]: `Error: ${err.message}` }))
    },
  })

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Tools Hub
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          {tools.length} tools · dynamically discovered from{' '}
          <code className="font-mono text-xs px-1.5 py-0.5 rounded"
                style={{ background: 'var(--bg-surface)', color: 'var(--accent-amber)' }}>
            /api/capabilities
          </code>
        </p>
      </div>

      <div className="space-y-2">
        {tools.map((tool, i) => {
          const open = expanded === tool
          const hasDryRun = tool in SAFE_TOOL_ENDPOINTS
          return (
            <motion.div
              key={tool}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="rounded-xl border overflow-hidden"
              style={{ background: 'var(--bg-surface)', borderColor: open ? 'rgba(245,158,11,0.4)' : 'var(--border)' }}
            >
              <button
                onClick={() => setExpanded(open ? null : tool)}
                className="w-full flex items-center justify-between px-4 py-3.5 text-left hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <code className="text-sm font-mono font-medium" style={{ color: 'var(--accent-amber)' }}>
                    {tool}
                  </code>
                </div>
                {open
                  ? <ChevronDown className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
                  : <ChevronRight className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />}
              </button>

              <AnimatePresence>
                {open && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    <div className="px-4 pb-4 space-y-3 border-t" style={{ borderColor: 'var(--border)' }}>
                      <p className="text-sm pt-3 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                        {TOOL_DOCS[tool] ?? 'No documentation available.'}
                      </p>

                      {hasDryRun && (
                        <button
                          onClick={() => run.mutate(tool)}
                          disabled={run.isPending && run.variables === tool}
                          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border transition-colors disabled:opacity-50"
                          style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6', borderColor: 'rgba(59,130,246,0.2)' }}
                        >
                          {run.isPending && run.variables === tool
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Play className="w-3 h-3" />}
                          Preview (read-only)
                        </button>
                      )}

                      {results[tool] && (
                        <pre
                          className="text-xs font-mono p-3 rounded-lg overflow-auto max-h-48 leading-relaxed"
                          style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}
                        >
                          {results[tool]}
                        </pre>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
