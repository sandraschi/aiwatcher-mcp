"""
Curated interest bundles - fleet-maintained presets (no LLM elicitation).

Each preset: feeds tuple list, bundle metadata, distillation system prompt.
Applied idempotently on init_db via ensure_fleet_bundle_presets().
"""

from __future__ import annotations

# (name, url, feed_type)
IDE_HOST_FEEDS: list[tuple[str, str, str]] = [
    ("Reddit r/cursor", "https://www.reddit.com/r/cursor/new/.rss", "rss"),
    ("Reddit r/CursorAI", "https://www.reddit.com/r/CursorAI/new/.rss", "rss"),
    (
        "HN Cursor MCP",
        "https://hnrss.org/newest?q=cursor+MCP&points=10",
        "rss",
    ),
    (
        "HN Cursor IDE",
        "https://hnrss.org/newest?q=cursor+IDE&points=15",
        "rss",
    ),
    (
        "HN Zed editor",
        "https://hnrss.org/newest?q=zed+editor&points=15",
        "rss",
    ),
    (
        "HN Windsurf IDE",
        "https://hnrss.org/newest?q=windsurf+IDE&points=10",
        "rss",
    ),
    (
        "Google News Cursor MCP",
        "https://news.google.com/rss/search?q=cursor+IDE+MCP+changelog&hl=en-US&gl=US&ceid=US:en",
        "rss",
    ),
    (
        "Cursor Forum latest",
        "https://forum.cursor.com/latest.rss",
        "rss",
    ),
    ("Zed Releases", "https://github.com/zed-industries/zed/releases.atom", "rss"),
    (
        "opencode Releases",
        "https://github.com/opencode-ai/opencode/releases.atom",
        "rss",
    ),
    (
        "Simon Willison Weblog",
        "https://simonwillison.net/atom/entries/",
        "rss",
    ),
    (
        "Simon Willison TIL",
        "https://til.simonwillison.net/tils.atom",
        "rss",
    ),
]

IDE_HOST_SYSTEM = """You are Sandra's IDE host signal analyst. She runs a 100+ repo MCP fleet
(Cursor primary, plus Zed, Windsurf, Antigravity, Claude Desktop, OpenCode).

Score items about HOST IDE behavior, developer tooling, FastMCP, Bun, LLM APIs, and agentic workflows - not generic AI hype.

RELEVANCE (0-10):
  9-10 = Direct host/tooling change she uses daily (Cursor MCP UI, approval/auto-review, memops,
         stdio proxy, FastMCP, Bun releases, uv, Claude Agent SDK, core CLI tools)
  7-8  = Peer IDE (Zed, Windsurf, VS Code Copilot agent, Claude Code) MCP or agent UX, technical TILs & deep dives
  5-6  = Indirect (model pricing, general web standards)
  0-4  = Skip - generic LLM news with no tooling impact, personal blog posts, bird photos, photography, travel notes

URGENCY (0-10):
  9-10 = Breaking workflow change NOW (approval blocked, MCP broken, silent behavior change,
         security regression, memops split-brain symptom)
  7-8  = Major tool upgrade / shipped UX not in official changelog yet (e.g. Bun major release, Claude SDK breaking change)
  5-6  = Useful within a week
  0-4  = Background

Always tag when applicable:
  host-ux, mcp-approval, changelog-gap, cursor, zed, windsurf, memops, auto-review, bun, toolchain

If item describes a change BEFORE cursor.com/changelog documents it, set urgency >= 8 and
tag changelog-gap.

Respond ONLY with valid JSON:
{
  "relevance": <float>,
  "urgency": <float>,
  "summary": "<2-3 sentences, dry technical, no hype>",
  "tags": ["tag1", "tag2"],
  "reason": "<one line why scored>"
}
"""

IDE_HOST_BUNDLE: dict[str, str | float] = {
    "name": "IDE Host Signal",
    "topic": "IDE host UX, MCP integration, agent approval - Cursor Zed Windsurf",
    "system_prompt": IDE_HOST_SYSTEM,
    "alert_threshold": 8.0,
}

# (name, url, feed_type)
FRONTIER_SAFETY_FEEDS: list[tuple[str, str, str]] = [
    (
        "Anthropic Research",
        "https://www.anthropic.com/research/rss",
        "rss",
    ),
    (
        "Anthropic News",
        "https://www.anthropic.com/news/rss",
        "rss",
    ),
    (
        "HN Frontier Red Team",
        "https://hnrss.org/newest?q=frontier+red+team+anthropic&points=10",
        "rss",
    ),
    (
        "Google News Anthropic Threat Intel",
        "https://news.google.com/rss/search?q=Anthropic+threat+intelligence+red+team&hl=en-US&gl=US&ceid=US:en",
        "rss",
    ),
    (
        "Google News AI targeting eval",
        "https://news.google.com/rss/search?q=AI+drone+targeting+evaluation+frontier&hl=en-US&gl=US&ceid=US:en",
        "rss",
    ),
    (
        "LessWrong",
        "https://www.lesswrong.com/feed.xml",
        "rss",
    ),
]

FRONTIER_SAFETY_SYSTEM = """You are Sandra's frontier safety analyst. She runs on-hyperwar (control-centric book on decision speed) and is pro-AI but tracking cost-collapse risk.

Score items about frontier capability evals, threat intel reports, safety classifiers, open-weights gap, and governance (compute controls, law, defender advantage) - not generic AI hype.

RELEVANCE (0-10):
  9-10 = Direct Anthropic Frontier Red Team / Threat Intel drop, new eval numbers on targeting or GNC, observed misuse case, classifier deployment
  7-8  = Peer lab safety eval (DeepMind, OpenAI, Meta), open-weights safety result (Kimi, GLM, DeepSeek, Qwen), governance move with teeth
  5-6  = General AI safety commentary with one actionable fact
  0-4  = Skip - hype, moral framing without numbers, vendor PR without eval detail

URGENCY (0-10):
  9-10 = New misuse pattern or eval showing civilian find/fix uplift NOW
  7-8  = New report / classifier / export rule within a week
  5-6  = Background reading
  0-4  = Noise

Summarize INSTITUTIONAL IMPLICATIONS ONLY: who reported what, when, what safeguard was claimed, why it does or does not cover low-end actors. Never reproduce TTP detail, method detail, scores beyond high-level, or code.

Always tag when applicable:
  frontier-eval, threat-intel, find-fix, GNC, classifier, open-weights, governance, on-hyperwar

Respond ONLY with valid JSON:
{
  "relevance": <float>,
  "urgency": <float>,
  "summary": "<2-3 sentences, dry technical, no hype>",
  "tags": ["tag1", "tag2"],
  "reason": "<one line why scored>"
}
"""

FRONTIER_SAFETY_BUNDLE: dict[str, str | float] = {
    "name": "Frontier Safety",
    "topic": "Frontier red team evals, threat intel, open-weights safety - Anthropic et al",
    "system_prompt": FRONTIER_SAFETY_SYSTEM,
    "alert_threshold": 7.5,
}

FLEET_BUNDLE_PRESETS: list[dict] = [
    {
        "feeds": IDE_HOST_FEEDS,
        "bundle": IDE_HOST_BUNDLE,
        "fleet_id": "ide-host-signal",
    },
    {
        "feeds": FRONTIER_SAFETY_FEEDS,
        "bundle": FRONTIER_SAFETY_BUNDLE,
        "fleet_id": "frontier-safety",
    },
]
