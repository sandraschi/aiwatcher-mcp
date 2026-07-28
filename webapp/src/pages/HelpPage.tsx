import {
  Activity,
  Bell,
  BookOpen,
  ChevronRight,
  Database,
  ExternalLink,
  Github,
  Mail,
  Terminal,
  Zap,
} from "lucide-react";
import { useState } from "react";

const SECTIONS = [
  {
    id: "quickstart",
    icon: Zap,
    title: "Quick Start",
    color: "text-amber-500",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    content: `1. Copy .env.example → .env and set ANTHROPIC_API_KEY.
2. Run start.bat (clears ports, starts backend :10946 and frontend :10947).
3. Click "Poll Feeds" on the Dashboard to ingest the first batch.
4. Click "Distill" to score items with Claude.
5. Browse scored items on the News Feed page.`,
  },
  {
    id: "alerts",
    icon: Bell,
    title: "Alert Pipeline",
    color: "text-rose-500",
    bg: "bg-rose-500/10",
    border: "border-rose-500/20",
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
    id: "email",
    icon: Mail,
    title: "Email Digest",
    color: "text-blue-500",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    content: `The daily HTML digest is generated at 06:00 UTC and sent to Sandra + Steve.

Recipients: EMAIL_RECIPIENTS (comma-separated)
Subject prefix: EMAIL_SUBJECT_PREFIX (default [AIWatcher])

Delivery priority:
  1. email-mcp REST  (EMAIL_MCP_URL — preferred if running on :10812)
  2. SMTP fallback   (SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD)

The digest HTML uses inline styles and renders well in Gmail, Outlook, and
Apple Mail. Claude generates it with a Sandra-persona prompt covering:
CRITICAL ALERTS → TOP STORIES → PORTFOLIO WATCH → TECH DEEP DIVE.

Force-send via the Digest page or: POST /api/digest/send

Intel Reports Hub (iPad / Tailscale):
  INTEL_REPORTS_HUB_URL=http://127.0.0.1:11027
  Daily digest HTML is POSTed to /api/reports/publish after email.
  Fritz Pulse and Day Prep reports land on the same hub index.`,
  },
  {
    id: "intel_hub",
    icon: BookOpen,
    title: "Intel Reports Hub",
    color: "text-violet-500",
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
    content: `Shared fleet HTML report index on port 11027 (fleet-agent-mcp).

AIWatcher publishes daily digest HTML after email/Calibre.
Fritz publishes Fleet Pulse, Day Prep, and home-safety (devices watch) reports.

Env: INTEL_REPORTS_HUB_URL (default http://127.0.0.1:11027)
Ensure hub: fleet-agent-mcp/scripts/start-intel-hub.ps1
           aiwatcher-mcp/scripts/ensure-intel-hub.ps1

iPad: http://<goliath-tailscale>:11027/
Funnel: tailscale funnel 11027

MCP help: aiwatcher_help(topic="intel_hub")
Pattern: mcp-central-docs/patterns/intel-reports-hub.md`,
  },
  {
    id: "fleet_pipeline",
    icon: Database,
    title: "Fleet Pipeline",
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    content: `Producer API (other fleet members push here):

POST /api/fleet/ingest
  title, summary, source, url, urgency_hint

Producers:
  arxiv-mcp code-hunt   source: arxiv-codehunt
  vla-mcp pipeline      source: vla-mcp-pipeline

Interest bundles (interests.json):
  China Open Weights  — Fleet Events, cs.SD/RO, FunASR
  VLA & Spatial AI    — Wall-OSS, X-VLA, Fleet Events
  Robotics            — embodied, VLA keywords

Upstream probes (GET /api/pipeline/liveness):
  ARXIV_MCP_URL=http://localhost:10770  (NOT 10719)
  VLA_MCP_URL=http://localhost:11024
  VLA_MCP_ENABLED=true

MCP: aiwatcher_help(topic="fleet_pipeline")
REST: GET /api/help/fleet_pipeline

Dashboard Pipeline Health card polls every 15s.
meta-mcp + fleet-agent aggregate all three pipeline endpoints.`,
  },
  {
    id: "api_keys",
    icon: Terminal,
    title: "API Keys",
    color: "text-orange-500",
    bg: "bg-orange-500/10",
    border: "border-orange-500/20",
    content: `AIWATCHER_API_KEY (optional REST auth on this server)

When UNSET (default):
  No X-AIWatcher-Key header needed on localhost.
  Fleet ingest from arxiv-mcp and vla-mcp works out of the box.

When SET:
  All /api/* routes require X-AIWatcher-Key or Authorization: Bearer
  EXCEPT: /health, /api/health, /metrics, /mcp

Mirror the SAME secret on producers:
  arxiv-mcp  ARXIV_MCP_AIWATCHER_API_KEY
  vla-mcp    VLA_AIWATCHER_API_KEY

NOT the same keys:
  ANTHROPIC_API_KEY  — distillation / scoring only
  DEEPSEEK_API_KEY     — cloud flash scoring only

MCP: aiwatcher_help(topic="api_keys")
If Pipeline Health shows 401, align keys or leave AIWATCHER_API_KEY empty.`,
  },
  {
    id: "integrations",
    icon: Database,
    title: "Integrations",
    color: "text-cyan-500",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/20",
    content: `robofang   ROBOFANG_BACKEND_URL=http://localhost:10871
               ROBOFANG_ENABLED=true

speechops  SPEECHOPS_HTTP_URL=http://localhost:10895
               (separate from MCP transport; direct HTTP)

email-mcp  EMAIL_MCP_URL=http://localhost:10812
               EMAIL_ENABLED=true

calibre    CALIBRE_MCP_URL=http://localhost:10720
               CALIBRE_ENABLED=true
               CALIBRE_LIBRARY=AI News

arxiv-mcp  ARXIV_ENABLED=true
               ARXIV_MCP_URL=http://localhost:10770

vla-mcp    VLA_MCP_ENABLED=true
               VLA_MCP_URL=http://localhost:11024

Gmail      GMAIL_ENABLED=true
               ALPHASIGNAL_SENDER=newsletter@alphasignal.ai`,
  },
  {
    id: "scoring",
    icon: Activity,
    title: "Scoring Model",
    color: "text-purple-500",
    bg: "bg-purple-500/10",
    border: "border-purple-500/20",
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
  {
    id: "mcp",
    icon: Terminal,
    title: "MCP API",
    color: "text-cyan-500",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/20",
    content: `Tools:
- poll_feeds, distill_pending, check_alerts, generate_digest
- get_top_items, search_items, get_bundle_health
- aiwatcher_help: In-chat docs (topic=fleet_pipeline, api_keys, …)
- show_dashboard_card: Prefab UI widget

REST help: GET /api/help  |  GET /api/help/{topic}

Prompts:
- breaking_news_brief, portfolio_impact_analysis`,
  },
];

export function HelpPage() {
  const [activeTab, setActiveTab] = useState(SECTIONS[0].id);

  const activeSection = SECTIONS.find((s) => s.id === activeTab);

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-zinc-900/50 to-zinc-800/30 border border-white/5 backdrop-blur-xl shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-500/20 border border-indigo-500/30 rounded-xl">
            <BookOpen className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/70">
              Documentation Hub
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              FastMCP 3.2 Fleet Server
            </p>
          </div>
        </div>
        <a
          href="https://github.com/sandraschi/aiwatcher-mcp"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border border-white/10 bg-white/5 hover:bg-white/10 transition-all duration-300 text-zinc-300 hover:text-white"
        >
          <Github className="w-4 h-4" />
          GitHub
          <ExternalLink className="w-3.5 h-3.5 opacity-50" />
        </a>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-[500px]">
        {/* Sidebar Nav */}
        <div className="w-full md:w-64 flex flex-col gap-2 shrink-0">
          {SECTIONS.map((section) => {
            const isActive = activeTab === section.id;
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                onClick={() => setActiveTab(section.id)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 text-left ${
                  isActive
                    ? "bg-white/10 border border-white/20 shadow-lg shadow-black/20"
                    : "hover:bg-white/5 border border-transparent opacity-70 hover:opacity-100"
                }`}
              >
                <div
                  className={`p-2 rounded-lg ${section.bg} ${section.border} border`}
                >
                  <Icon className={`w-4 h-4 ${section.color}`} />
                </div>
                <span
                  className={`text-sm font-medium ${isActive ? "text-white" : "text-zinc-300"}`}
                >
                  {section.title}
                </span>
                {isActive && (
                  <ChevronRight className="w-4 h-4 ml-auto text-zinc-500" />
                )}
              </button>
            );
          })}
        </div>

        {/* Content Pane */}
        <div className="flex-1 rounded-2xl border border-white/10 bg-zinc-900/40 backdrop-blur-md overflow-hidden relative group">
          {/* Subtle gradient glow behind the content pane */}
          <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

          {activeSection && (
            <div className="p-8 h-full flex flex-col animate-in fade-in slide-in-from-right-4 duration-500">
              <div className="flex items-center gap-4 mb-8 pb-6 border-b border-white/5">
                <div
                  className={`p-3 rounded-xl ${activeSection.bg} ${activeSection.border} border`}
                >
                  <activeSection.icon
                    className={`w-6 h-6 ${activeSection.color}`}
                  />
                </div>
                <h2 className="text-2xl font-semibold text-white tracking-tight">
                  {activeSection.title}
                </h2>
              </div>

              <div className="flex-1 overflow-auto custom-scrollbar pr-4">
                <pre className="text-sm text-zinc-300 font-mono leading-relaxed whitespace-pre-wrap">
                  {activeSection.content}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
