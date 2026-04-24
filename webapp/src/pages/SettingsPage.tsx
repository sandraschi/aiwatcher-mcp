import { useQuery } from '@tanstack/react-query'
import { Settings2, Bell, Mail, Database, Zap } from 'lucide-react'

async function fetchCaps() {
  const r = await fetch('/api/capabilities')
  return r.json()
}

export function SettingsPage() {
  const { data } = useQuery({ queryKey: ['capabilities'], queryFn: fetchCaps })

  const integrations = data?.integrations ?? {}
  const features = data?.features ?? {}

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
        Settings
      </h1>

      <section className="rounded-xl border p-5 space-y-4"
               style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2 mb-1">
          <Zap className="w-4 h-4" style={{ color: 'var(--accent-amber)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Runtime Capabilities
          </h2>
        </div>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Live from <code className="font-mono">/api/capabilities</code> — reflects actual server state.
          Configure via <code className="font-mono">.env</code> and restart.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries({
            ...features,
            ...Object.fromEntries(Object.entries(integrations).map(([k, v]) => [`${k} (integration)`, v])),
          }).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between px-3 py-2 rounded-lg"
                 style={{ background: 'var(--bg-primary)' }}>
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                {key.replace(/_/g, ' ')}
              </span>
              <span className={`text-xs font-mono font-medium ${value ? 'text-green-500' : 'text-zinc-600'}`}>
                {value ? 'ON' : 'OFF'}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border p-5 space-y-3"
               style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <Settings2 className="w-4 h-4" style={{ color: 'var(--accent-amber)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Configuration Reference
          </h2>
        </div>
        <div className="text-xs space-y-1.5 font-mono" style={{ color: 'var(--text-secondary)' }}>
          {[
            ['ANTHROPIC_API_KEY', 'Claude distillation model key'],
            ['ALERT_THRESHOLD', 'Urgency score for wake-up (default 8.5)'],
            ['ALERT_HOUR_UTC', 'Alert check time UTC (default 4 = 5am Vienna)'],
            ['FEED_POLL_INTERVAL_MINUTES', 'Feed poll cadence (default 30)'],
            ['ROBOFANG_ENABLED', 'true/false — push alerts to robofang'],
            ['EMAIL_ENABLED', 'true/false — send digest emails'],
            ['EMAIL_RECIPIENTS', 'Comma-separated recipient addresses'],
            ['CALIBRE_ENABLED', 'true/false — ingest digests to Calibre'],
            ['GMAIL_ENABLED', 'true/false — parse Alpha Signal from Gmail'],
          ].map(([key, desc]) => (
            <div key={key} className="flex gap-3">
              <span className="text-amber-400 flex-shrink-0">{key}</span>
              <span style={{ color: 'var(--text-muted)' }}>{desc}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border p-5 space-y-3"
               style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4" style={{ color: 'var(--accent-amber)' }} />
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Alert Pipeline
          </h2>
        </div>
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Daily at 04:55 UTC (05:55 Vienna summer / 05:55 CET winter):
          items scored ≥ ALERT_THRESHOLD trigger robofang Council POST
          and speechops TTS wake-up. Windows SAPI5 is the fallback if
          speechops HTTP is unreachable.
        </p>
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Daily digest email fires at 06:00 UTC (07:00 Vienna).
          Recipients: Sandra + Steve. Format: HTML email with inline styles.
        </p>
      </section>
    </div>
  )
}
