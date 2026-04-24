import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { ExternalLink, Circle } from 'lucide-react'

// Fleet discovery: probe the well-known fleet port range for live webapps.
// We check /api/health or /health on each registered port.
// This mirrors the fleet discovery pattern from WEBAPP_SOTA_STANDARDS §III.
const FLEET_PORTS: Array<{ port: number; name: string; repo: string }> = [
  { port: 10704, name: 'Advanced Memory', repo: 'advanced-memory-mcp' },
  { port: 10718, name: 'Meta MCP', repo: 'meta_mcp' },
  { port: 10720, name: 'Calibre', repo: 'calibre-mcp' },
  { port: 10738, name: 'Dark App Factory', repo: 'dark-app-factory' },
  { port: 10740, name: 'Plex', repo: 'plex-mcp' },
  { port: 10748, name: 'Windows Ops', repo: 'windows-operations-mcp' },
  { port: 10756, name: 'Discord', repo: 'discord-mcp' },
  { port: 10770, name: 'arXiv', repo: 'arxiv-mcp' },
  { port: 10812, name: 'Email', repo: 'email-mcp' },
  { port: 10816, name: 'ToolBench', repo: 'toolbench-mcp' },
  { port: 10850, name: 'Monitoring', repo: 'monitoring-mcp' },
  { port: 10864, name: 'World Labs', repo: 'worldlabs-mcp' },
  { port: 10870, name: 'RoboFang', repo: 'robofang' },
  { port: 10892, name: 'Yahboom', repo: 'yahboom-mcp' },
  { port: 10898, name: 'MagentArt', repo: 'magentart-mcp' },
  { port: 10942, name: 'Ednaficator', repo: 'ednaficator' },
  { port: 10946, name: 'AIWatcher ★', repo: 'aiwatcher-mcp' },
]

async function probePort(port: number): Promise<boolean> {
  try {
    const r = await fetch(`http://localhost:${port}/api/health`, {
      signal: AbortSignal.timeout(1500),
    })
    return r.ok
  } catch {
    try {
      const r = await fetch(`http://localhost:${port}/health`, {
        signal: AbortSignal.timeout(1500),
      })
      return r.ok
    } catch {
      return false
    }
  }
}

async function discoverFleet() {
  const results = await Promise.allSettled(
    FLEET_PORTS.map(async (entry) => ({
      ...entry,
      alive: await probePort(entry.port),
    }))
  )
  return results.map((r) => (r.status === 'fulfilled' ? r.value : null)).filter(Boolean)
}

export function AppsPage() {
  const { data: apps, isLoading } = useQuery({
    queryKey: ['fleet-discovery'],
    queryFn: discoverFleet,
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  const alive = apps?.filter((a) => a?.alive) ?? []
  const dead = apps?.filter((a) => !a?.alive) ?? []

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
          Fleet Apps Hub
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
          Dynamic discovery of active MCP webapps on localhost — probing {FLEET_PORTS.length} registered ports
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl animate-pulse" style={{ background: 'var(--bg-surface)' }} />
          ))}
        </div>
      ) : (
        <>
          {alive.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Online ({alive.length})
              </h2>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                {alive.map((app, i) => app && (
                  <motion.a
                    key={app.port}
                    href={`http://localhost:${app.port}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.04 }}
                    className="rounded-xl border p-4 flex flex-col gap-2 hover:border-zinc-500 transition-colors group"
                    style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Circle className="w-2 h-2 fill-green-500 text-green-500" />
                        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                          {app.name}
                        </span>
                      </div>
                      <ExternalLink className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                    style={{ color: 'var(--text-muted)' }} />
                    </div>
                    <div className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                      :{app.port}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {app.repo}
                    </div>
                  </motion.a>
                ))}
              </div>
            </section>
          )}

          {dead.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
                Offline ({dead.length})
              </h2>
              <div className="grid grid-cols-3 lg:grid-cols-4 gap-2">
                {dead.map((app) => app && (
                  <div
                    key={app.port}
                    className="rounded-lg border px-3 py-2 flex items-center gap-2"
                    style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', opacity: 0.45 }}
                  >
                    <Circle className="w-2 h-2 flex-shrink-0" style={{ color: 'var(--text-muted)' }} />
                    <div className="min-w-0">
                      <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{app.name}</div>
                      <div className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>:{app.port}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
