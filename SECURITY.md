# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: sandra@theagenticmines.at

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

Expect a response within 72 hours. Confirmed vulnerabilities will be patched
in the next release and credited in `CHANGELOG.md` unless anonymity is requested.

## Threat Model

aiwatcher-mcp is a **local fleet server** intended to run on a trusted personal
machine. It is not designed for public internet exposure. Key threat surface:

| Component | Risk | Mitigation |
|-----------|------|------------|
| `ANTHROPIC_API_KEY` in `.env` | Key theft → API charges | `.env` gitignored; never committed |
| Starlette REST `:10946` | SSRF via feed URLs | `httpx` with timeout=20; no user-supplied redirects |
| aiosqlite WAL | Concurrent write corruption | Single `get_db()` context manager; WAL mode enabled |
| RSS feed content | XSS in digest HTML | Jinja2 autoescaping; `premailer` inlines styles |
| robofang / speechops POSTs | Injection via item title/summary | JSON serialization; no shell interpolation |
| **RSS/Atom feed items → LLM** | **Prompt injection via feed title/summary** — attacker embeds "ignore all previous instructions" in a blog title; LLM autocorrects and follows it | **Dual defense: (1) `scrubber.py`** — regex blocklist + URL blocklist filters spam/scam items at ingest before they reach the LLM. **(2) Safety preamble** — `distillation.py::ITEM_PROMPT` prepends `_SAFETY_WRAP` warning before untrusted content, telling the LLM to treat it as data, not instructions. |

## Spam Scrubber

Inbound items are classified by `src/aiwatcher_mcp/scrubber.py` at every ingest boundary:
- **Layer 1 (regex)**: 22 patterns for known spam (get-rich-quick, crypto scams, phishing, weight loss, SEO junk)
- **Layer 1b (URL)**: Shortener domain check + user-extensible blocklist at `data/spam_blocklist.txt`
- Spam items are tagged `["spam"]`, still inserted (visible in UI), but excluded from distillation via `json_each` filter in `get_undistilled_bundle_items()`
- Blocklist is hot-reloadable via `scrubber_reload` MCP tool — no restart needed

## Secrets Handling

- All secrets via environment variables only — never hardcoded
- `.env` is gitignored
- `.env.example` contains only placeholder values
- `ANTHROPIC_API_KEY` is the only required secret
- SMTP password and Gmail credentials are optional and off by default

## Dependency Security

Dependencies are pinned in `uv.lock`. Run `uv lock --upgrade` periodically
and review the diff before committing. Dependabot is configured to open PRs
for outdated dependencies (see `.github/dependabot.yml`).
