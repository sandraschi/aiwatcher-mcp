# aiwatcher-mcp Architecture

## High-Level Overview

`aiwatcher-mcp` operates as a central nervous system for AI intelligence. It continuously ingests data from various feeds, applies LLM-driven filtering and scoring (distillation) to bubble up the most critical information, and dispatches alerts via the Antigravity fleet based on urgency thresholds.

```mermaid
graph TD
    subgraph Ingestion
        A[RSS/Atom Feeds] --> S[Spam Scrubber]
        B[Gmail - Alpha Signal] --> S
        AR[ArXiv Papers] --> S
        R[Readly Articles] --> S
        S -->|legit items| C(SQLite DB)
        S -->|scam/spam| D[tagged [spam] + inserted]
        D --> C
    end

    subgraph Processing
        C -->|Raw Items (excl. spam)| E{APScheduler Job}
        E -->|Batch| F[Claude Distillation]
        F -->|Safety-wrapped prompt| F
        F -->|Scored & Summarized| C
    end

    subgraph Alerting
        C -->|Urgency >= 8.5| F[robofang Council POST]
        C -->|Urgency >= 8.5| G[speechops TTS wake-up]
    end

    subgraph Delivery
        C -->|06:00 UTC Daily| H[HTML Digest Generation]
        H --> I[email-mcp Delivery]
        H --> J[calibre-mcp Archive]
    end
```

## Core Components

### 0. Spam Scrubber (`scrubber.py`)
All inbound items pass through a lightweight classifier before storage:
- **Layer 1 (regex)**: 22 patterns for known spam vectors (get-rich-quick, crypto scams, phishing, SEO junk)
- **Layer 1b (URL)**: Shortener domain check + user-extensible `data/spam_blocklist.txt`
- **Layer 2 (future)**: Local LLM classification for borderline cases
- Spam items are tagged `["spam"]` and excluded from Claude distillation
- Blocklist is hot-reloadable via `scrubber_reload` MCP tool

### 1. Ingestion Pipeline
- **RSS/Atom Pollers:** Fetches XML feeds (e.g., Anthropic, OpenAI, general tech news) using `feedparser`.
- **Gmail Integration (Optional):** Hooks into the `email-mcp` or direct Gmail OAuth to parse links from trusted newsletters like Alpha Signal.

### 2. Distillation Engine (Claude)
New items are batched and sent to Claude (using `claude-sonnet-4-20250514`). The prompt instructs Claude to adopt the "Sandra" persona and evaluate each item on two axes:
- **Relevance (0-10):** How much does it affect her tooling, fleet, or portfolio?
- **Urgency (0-10):** Is this breaking news requiring immediate action?
Claude also generates a concise summary and assigns categorization tags.

**Safety**: The `ITEM_PROMPT` prepends a `_SAFETY_WRAP` preamble before the untrusted item content, telling the LLM to treat it as data not instructions — mitigating prompt injection vectors where an attacker embeds "ignore all previous instructions" in a feed item.

### 3. APScheduler
Background jobs run independently of the FastMCP lifecycle:
- **`poll_feeds`:** Runs every 15-30 minutes.
- **`distill_pending`:** Runs shortly after ingestion batches.
- **`morning_alert`:** Triggers at `04:55 UTC` to evaluate overnight data for critical wake-up events.
- **`digest_sender`:** Triggers at `06:00 UTC` to dispatch the daily HTML digest.

### 4. Fleet Integration (The Alert Pipeline)
Items breaching the `ALERT_THRESHOLD` trigger cross-server communications:
- **robofang:** Breaking events are pushed via HTTP POST to the Council bridge (`port 10871`).
- **speechops:** A TTS payload is sent (`port 10895`) to wake up Sandra if she is asleep. SAPI5 is used as a local fallback.

### 5. Web App (Prefab UI & Vite)
The server exposes an MCP application via Prefab UI (`show_dashboard_card`). In addition, a standalone Vite/React web application runs on port `10947` for full visual browsing of news feeds, configuration, and digest history.

## Database Schema (SQLite)

- **`feeds`**: `id`, `name`, `url`, `feed_type`, `last_fetched`, `is_active`
- **`items`**: `id`, `feed_id`, `guid`, `title`, `url`, `published_at`, `raw_content`
- **`distillation`**: `item_id`, `relevance_score`, `urgency_score`, `distilled_summary`, `tags`, `processed_at`
- **`digests`**: `id`, `generated_at`, `html_body`, `sent_status`
