# aiwatcher-mcp — TODO / Action Items

**Last reviewed:** 2026-06-03 — **0.1.6** release (P0–P4 complete)  
**Next epic:** P1 Readly watchlist pipeline (blocked on readly-mcp 0.2.1 — see cross-repo TODO)

---

## Completed (0.1.6)

- v0.2.0 features F1–F5, Fritz/federation, seed-feeds, digest cache, DB pool, security, tests
- P4: feed decay, fuzzy summary dedup, fleet events, trends, portfolio watch, digest tones, `/metrics`
- Playwright e2e: `webapp/e2e/`, `just e2e` (18 specs, ports 10946/10947)
- Docs: PRD, API, ARCHITECTURE, CHANGELOG, README, ASSESSMENT

---

## P1 — Readly watchlist pipeline

<!-- Cross-project: D:\Dev\repos\mcp-central-docs\operations\INTEL_STACK_TODO.md CROSS-1 -->
<!-- Prerequisite: D:\Dev\repos\mcp-central-docs\projects\readly-mcp\TODO.md P1 endpoints -->

readly-mcp v0.2 calls exist (`/api/articles/list`, `/api/articles/extract`). Watchlist needs
`GET /api/magazines/latest?name=X` and `GET /api/articles/read-all?max=N` from readly-mcp **0.2.1**.

### 1. `READLY_WATCHLIST` env — `src/aiwatcher_mcp/config.py` + `.env.example`

```python
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing fields ...

    readly_enabled: bool = Field(default=False, alias="READLY_ENABLED")
    readly_mcp_url: str = Field(default="http://localhost:10863", alias="READLY_MCP_URL")
    readly_watchlist: list[str] = Field(
        default_factory=list,
        description="Magazine names to poll via readly-mcp watchlist API",
    )
    readly_poll_max_articles: int = Field(default=10, alias="READLY_POLL_MAX_ARTICLES")
    readly_poll_interval_hours: int = Field(default=6, alias="READLY_POLL_INTERVAL_HOURS")

    @field_validator("readly_watchlist", mode="before")
    @classmethod
    def _parse_readly_watchlist(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        # Comma-separated from env: "New Scientist,MIT Technology Review,c't"
        return [part.strip() for part in str(v).split(",") if part.strip()]
```

```env
# .env.example
READLY_ENABLED=false
READLY_MCP_URL=http://localhost:10863
READLY_WATCHLIST=New Scientist,MIT Technology Review,c't,Wired,Die Presse,NZZ,IEEE Spectrum
READLY_POLL_MAX_ARTICLES=10
READLY_POLL_INTERVAL_HOURS=6
```

Runtime watchlist (MCP tool) can override in-memory list without restart — persist optional P2.

---

### 2. Per-magazine feed IDs — `readly_ingestion.py`

Replace global `READLY_FEED_ID` cache with per-magazine rows:

```python
_FEED_CACHE: dict[str, int] = {}

async def _get_or_create_readly_feed(magazine_name: str) -> int:
    """One feed row per magazine: name='Readly: {magazine_name}', feed_type='readly'."""
    key = magazine_name.strip()
    if key in _FEED_CACHE:
        return _FEED_CACHE[key]

    feed_name = f"Readly: {key}"
    feed_url = f"readly://magazine/{key.lower().replace(' ', '-')}"

    async with get_db() as db:
        async with db.execute(
            "SELECT id FROM feeds WHERE name=? AND feed_type='readly'",
            (feed_name,),
        ) as cur:
            row = await cur.fetchone()
        if row:
            _FEED_CACHE[key] = row["id"]
            return row["id"]

        cur = await db.execute(
            "INSERT INTO feeds(name, url, feed_type, enabled) VALUES (?,?,?,1)",
            (feed_name, feed_url, "readly"),
        )
        await db.commit()
        _FEED_CACHE[key] = cur.lastrowid
        log.info("Created readly feed id=%d name=%s", cur.lastrowid, feed_name)
        return cur.lastrowid
```

---

### 3. Rewrite `poll_readly_articles()` — full watchlist loop + `content_html`

**File:** `src/aiwatcher_mcp/readly_ingestion.py` — replace entire function.

```python
async def poll_readly_articles() -> int:
    """
    Poll READLY_WATCHLIST magazines via readly-mcp watchlist API.
    Stores full article text in content_html for longform distillation.
    """
    cfg = get_settings()
    if not cfg.readly_enabled or not cfg.readly_mcp_url:
        return 0
    if not cfg.readly_watchlist:
        log.debug("Readly enabled but READLY_WATCHLIST empty — skip")
        return 0

    readly_url = cfg.readly_mcp_url.rstrip("/")
    max_articles = cfg.readly_poll_max_articles
    new_count = 0
    scrubber = Scrubber()

    timeout = httpx.Timeout(120.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for magazine_name in cfg.readly_watchlist:
            try:
                nav = await client.get(
                    f"{readly_url}/api/magazines/latest",
                    params={"name": magazine_name},
                )
                if nav.status_code != 200:
                    log.warning("Readly: latest issue HTTP %s for '%s'", nav.status_code, magazine_name)
                    continue
                nav_body = nav.json()
                if not nav_body.get("success"):
                    log.warning(
                        "Readly: could not open '%s': %s",
                        magazine_name,
                        nav_body.get("error", "unknown"),
                    )
                    continue

                batch = await client.get(
                    f"{readly_url}/api/articles/read-all",
                    params={"max": max_articles},
                )
                if batch.status_code != 200:
                    log.warning("Readly: read-all HTTP %s for '%s'", batch.status_code, magazine_name)
                    continue
                data = batch.json()
                if data.get("extraction_failed") or not data.get("articles"):
                    log.warning(
                        "Readly: no articles for '%s' (%s)",
                        magazine_name,
                        data.get("reason") or data.get("error") or "empty",
                    )
                    continue

                feed_id = await _get_or_create_readly_feed(magazine_name)
                await _ensure_bundle_for_magazine(magazine_name, feed_id)

                for article in data.get("articles", []):
                    text = (article.get("text") or "").strip()
                    wc = article.get("word_count") or len(text.split())
                    if wc < 50:
                        continue

                    url = article.get("url") or ""
                    title = article.get("title") or "(no title)"
                    guid = hashlib.sha256(
                        f"readly:{magazine_name}:{url or title}".encode()
                    ).hexdigest()[:32]

                    slug = magazine_name.lower().replace(" ", "-")
                    item = {
                        "guid": guid,
                        "title": title,
                        "url": url,
                        "summary": text[:500],
                        "content_html": text,
                        "published_at": None,
                        "tags": [
                            "readly",
                            "magazine",
                            "longform",
                            slug,
                            f"readly:{slug}",
                        ],
                    }

                    result, reason = scrubber.check_item(item)
                    if result in ("spam", "scam"):
                        log.info("Readly scrubber blocked '%s': %s", title[:60], reason)
                        continue

                    if await upsert_item(feed_id, item):
                        new_count += 1

            except Exception as exc:
                log.warning("Readly poll failed for '%s': %s", magazine_name, exc)

    log.info(
        "Readly: %d new articles across %d magazines",
        new_count,
        len(cfg.readly_watchlist),
    )
    return new_count
```

**Key change:** `content_html` holds full text (not `None` / 500-char summary only).

**Fallback (until readly 0.2.1):** Keep legacy single-page path behind env
`READLY_LEGACY_POLL=1` or detect 404 on `/api/magazines/latest`.

---

### 4. Auto-create bundle per magazine — `readly_ingestion.py`

```python
async def _ensure_bundle_for_magazine(magazine_name: str, feed_id: int) -> int | None:
    """Create interest bundle + link feed if missing. Returns bundle_id."""
    from aiwatcher_mcp.bundles import elicit_bundle_config
    from aiwatcher_mcp.database import add_bundle, get_bundles, link_feed_to_bundle

    topic = magazine_name.strip()
    bundles = await get_bundles()
    for b in bundles:
        if (b.get("topic") or "").lower() == topic.lower():
            await link_feed_to_bundle(feed_id, b["id"])
            return b["id"]

    config = await elicit_bundle_config(
        f"{topic} — longform magazine journalism; score for depth, investigative quality, "
        f"and relevance to AI, science, and technology policy"
    )
    bundle_id = await add_bundle(
        name=config.get("name") or f"Readly: {topic}",
        topic=topic,
        system_prompt=config["system_prompt"],
    )
    await link_feed_to_bundle(feed_id, bundle_id)
    log.info("Auto-created bundle id=%d for Readly magazine '%s'", bundle_id, topic)
    return bundle_id
```

Run only on **first** feed creation for that magazine (not every poll) — guard with DB lookup above.

---

### 5. APScheduler job — `src/aiwatcher_mcp/scheduler.py`

```python
async def _job_poll_readly() -> None:
    from aiwatcher_mcp.readly_ingestion import poll_readly_articles

    cfg = get_settings()
    if not cfg.readly_enabled:
        return
    count = await poll_readly_articles()
    log.info("Scheduled readly poll: %d new articles", count)


def start_scheduler() -> None:
    cfg = get_settings()
    sched = get_scheduler()
    # ... existing jobs ...

    if cfg.readly_enabled and cfg.readly_watchlist:
        sched.add_job(
            _job_poll_readly,
            trigger=IntervalTrigger(hours=cfg.readly_poll_interval_hours),
            id="readly_poll",
            replace_existing=True,
            misfire_grace_time=600,
        )
```

Remove readly from `poll_all_feeds()` interval poll **or** gate with `READLY_SCHEDULER_ONLY=1`
to avoid double-polling every 30m + every 6h. Recommended: **scheduler only**; keep manual MCP
`poll_feeds` triggering readly when explicitly requested.

---

### 6. `readly_watchlist` MCP tool — `src/aiwatcher_mcp/server.py`

```python
# Module-level runtime override (optional; env is source of truth on restart)
_runtime_readly_watchlist: list[str] | None = None


@mcp.tool()
async def readly_watchlist(action: str = "get", magazines: str = "") -> dict:
    """
    Get or mutate the Readly magazine watchlist at runtime.

    action: get | set | add | remove
    magazines: comma-separated names (required for set/add/remove)

    Env READLY_WATCHLIST is loaded on startup; runtime changes are in-memory until restart
    unless persisted (P2: write to .env or SQLite settings table).
    """
    global _runtime_readly_watchlist
    cfg = get_settings()
    current = (
        _runtime_readly_watchlist
        if _runtime_readly_watchlist is not None
        else list(cfg.readly_watchlist)
    )

    act = (action or "get").lower().strip()
    if act == "get":
        return {
            "watchlist": current,
            "count": len(current),
            "readly_enabled": cfg.readly_enabled,
            "readly_mcp_url": cfg.readly_mcp_url,
            "poll_interval_hours": cfg.readly_poll_interval_hours,
        }

    parts = [p.strip() for p in magazines.split(",") if p.strip()]
    if act == "set":
        if not parts:
            return {"error": "magazines required for set"}
        _runtime_readly_watchlist = parts
    elif act == "add":
        if not parts:
            return {"error": "magazines required for add"}
        merged = list(current)
        for p in parts:
            if p not in merged:
                merged.append(p)
        _runtime_readly_watchlist = merged
    elif act == "remove":
        if not parts:
            return {"error": "magazines required for remove"}
        remove_set = {p.lower() for p in parts}
        _runtime_readly_watchlist = [m for m in current if m.lower() not in remove_set]
    else:
        return {"error": f"unknown action: {action}"}

    return {
        "action": act,
        "watchlist": _runtime_readly_watchlist,
        "count": len(_runtime_readly_watchlist),
    }
```

Wire `poll_readly_articles()` to use `_runtime_readly_watchlist` when set:

```python
def _effective_readly_watchlist() -> list[str]:
    from aiwatcher_mcp.server import _runtime_readly_watchlist  # or move to config module
    cfg = get_settings()
    if _runtime_readly_watchlist is not None:
        return _runtime_readly_watchlist
    return list(cfg.readly_watchlist)
```

---

### 7. Tests (add after implementation)

| Test | File |
|------|------|
| `READLY_WATCHLIST` comma parse | `tests/test_config.py` |
| Watchlist poll mock httpx | `tests/test_readly_ingestion.py` |
| Scheduler registers `readly_poll` when enabled | `tests/test_scheduler.py` |
| `readly_watchlist` MCP get/set | `tests/test_server.py` |

---

### 8. Implementation order

1. Wait for / implement readly-mcp P1 (`magazines/latest`, `articles/read-all`)
2. aiwatcher config + `readly_ingestion.py` rewrite
3. Scheduler job + remove duplicate from `poll_all_feeds` if desired
4. MCP `readly_watchlist` tool
5. Tests + bump **0.1.7**, CHANGELOG, `docs/API.md`

---

## Backlog (v0.3+)

| Item | Target | Notes |
|------|--------|-------|
| `/api/items` cursor pagination | v0.3 | offset/limit exists; stable cursors |
| Embedding semantic dedup | v0.3 | fuzzy title+summary shipped in 0.1.6 |
| Vite sends `X-AIWatcher-Key` when auth on | v0.3 | Settings page |
| Persist runtime watchlist to DB | v0.3 | Beyond in-memory MCP tool |
| Fritz longform urgency rules | v0.3 | INTEL_STACK CROSS-4 |
| Calibre RAG over digests | v0.4 | Semantic search archive |
| Digest feedback loop | v0.4 | Per-item ratings |
| `manifest.json` icon asset | ops | Ship `assets/icon.png` |

---

## Summary

| Open P1 | Readly watchlist (7 items above) — blocked on readly-mcp 0.2.1 |
| Backlog | 8 roadmap items |
| Done | 0.1.6 + Playwright e2e |
