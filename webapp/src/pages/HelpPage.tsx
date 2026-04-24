import { BookOpen, Zap, Bell, Mail, Database, Github, ExternalLink } from 'lucide-react'

const SECTIONS = [
  {
    icon: Zap,
    title: 'Quick Start',
    content: `1. Copy .env.example → .env and set ANTHROPIC_API_KEY.
2. Run start.bat (clears ports, starts backend :10946 and frontend :10947).
3. Click "Poll Feeds" on the Dashboard to ingest the first batch.
4. Click "Distill" to score items with Claude.
5. Browse scored items on the News Feed page.`,
  },
  {
    icon: Bell,
    title: 'Alert Pipeline',
    content: `Items scored ≥ ALERT_THRESHOLD (default 8.5) trigger the alert pipeline:

→ robofang Council POST  (ROBOFANG_BACKEND_URL/api/v1/events)
→ speechops TTS         (SPEECHOPS_HTTP_URL/api/v1/tts)
→ Windows SAPI5         (fallback if speechops unreachable)

The scheduler runs this at 04:55 UTC daily (05:55 Vienna CET / 06:55 CEST).
You can also trigger it manually via "Check Alerts" on the Dashboard.

What counts as critical (urgency ≥ 8.5):
  • M&A involving tools you use (Cursor/Windsurf/Anthropic/xAI)
  • Major model releases (GPT-6, Claude 5, Gemini 5)
  • Security vulnerabilities in AI infrastructure
  • Regulatory shocks (EU AI Act enforcement actions)`,
  },
  {
    icon: Mail,
    title: 'Email Digest',
    content: `The daily HTML digest is generated at 06:00 UTC and sent to Sandra + Steve.

Recipients: EMAIL_RECIPIENTS (comma-separated)
Subject prefix: EMAIL_SUBJECT_PREFIX (default [AIWatcher])

Delivery priority:
  1. email-mcp REST  (EMAIL_MCP_URL — preferred if running on :10812)
  2. SMTP fallback   (SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD)

The digest HTML uses inline styles and renders well in Gmail, Outlook, and
Apple Mail. Claude generates it with a Sandra-persona prompt covering:
CRITICAL ALERTS → TOP STORIES → PORTFOLIO WATCH → TECH DEEP DIVE.

Force-send via the Digest page or: POST /api/digest/send`,
  },
  {
    icon: Database,
    title: 'Integrations',
    content: `robofang   ROBOFANG_BACKEND_URL=http://localhost:10871
               ROBOFANG_ENABLED=true

speechops  SPEECHOPS_HTTP_URL=http://localhost:10895
               (separate from MCP transport; direct HTTP)

email-mcp  EMAIL_MCP_URL=http://localhost:10812
               EMAIL_ENABLED=true

calibre    CALIBRE_MCP_URL=http://localhost:10720
               CALIBRE_ENABLED=true
               CALIBRE_LIBRARY=AI News
               (digests saved as ebooks in the AI News library)

Gmail      GMAIL_ENABLED=true
               GMAIL_MCP_URL=http://localhost:10812
               ALPHASIGNAL_SENDER=newsletter@alphasignal.ai
               (extracts article links from Alpha Signal emails hourly)`,
  },
  {
    icon: BookOpen,
    title: 'Scoring Model',
    content: `Claude scores each item 0–10 on two axes:

RELEVANCE — How much does Sandra care?
  10    Directly affects her tooling/fleet/portfolio
  8–9   Major AI capability release
  6–7   Significant ecosystem news
  4–5   Interesting but not actionable
  0–3   Generic tech with thin AI angle

URGENCY — How time-sensitive?
  9–10  BREAKING — immediate attention needed
  7–8   High — read within hours
  5–6   Medium — daily digest worthy
  0–4   Background — weekly roundup level

Alert threshold: ALERT_THRESHOLD (default 8.5 urgency).
The scoring uses claude-sonnet-4-20250514 via DISTILLATION_MODEL.`,
  },
]

export function HelpPage() {
  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Documentation
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            aiwatcher-mcp v0.1.0 — AI news intelligence for Sandra's fleet
          </p>
        </div>
        <a
          href="https://github.com/sandraschi/aiwatcher-mcp"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm border transition-colors hover:border-zinc-500"
          style={{ background: 'var(--bg-surface)', color: 'var(--text-secondary)', borderColor: 'var(--border)' }}
        >
          <Github className="w-4 h-4" />
          GitHub
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      <div className="space-y-3">
        {SECTIONS.map(({ icon: Icon, title, content }) => (
          <div
            key={title}
            className="rounded-xl border p-5 space-y-3"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                   style={{ background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)' }}>
                <Icon className="w-3.5 h-3.5" style={{ color: 'var(--accent-amber)' }} />
              </div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {title}
              </h2>
            </div>
            <pre
              className="text-xs leading-relaxed whitespace-pre-wrap font-mono"
              style={{ color: 'var(--text-secondary)' }}
            >
              {content}
            </pre>
          </div>
        ))}
      </div>
    </div>
  )
}
