# Contributing to aiwatcher-mcp

## Development Setup

```powershell
git clone https://github.com/sandraschi/aiwatcher-mcp
cd aiwatcher-mcp
copy .env.example .env
# Set ANTHROPIC_API_KEY in .env
just install   # uv sync + pre-commit install + npm
```

`just install` runs `pre-commit install` automatically. Adding `.pre-commit-config.yaml` without that step leaves hooks **inactive** until you run install.

## Running Tests

```powershell
just test
# or directly:
uv run pytest -v
```

## Code Quality

All PRs must pass:

```powershell
just lint       # ruff check
just fmt        # ruff format
just typecheck  # ty check
just test       # pytest
```

### Pre-commit

Hooks: `.pre-commit-config.yaml` (ruff + ruff-format on `src/` and `tests/`).

```powershell
just install            # activates hooks (preferred)
just pre-commit-install # re-run hook install only
just pre-commit-run     # manual full run
```

CI runs the same ruff checks on **windows-latest** (tag push + workflow_dispatch only).

## Branch Strategy

- `main` — stable, fleet-deployed
- `dev` — integration branch
- Feature branches: `feat/<short-name>`
- Bug fixes: `fix/<short-name>`

## Commit Style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(ingestion): add OPML batch import
fix(alerting): prevent duplicate robofang POSTs on restart
refactor(distillation): extract LLM provider interface
docs: update fleet port table in README
```

## Pull Request Checklist

- [ ] Tests added or updated
- [ ] `just lint` passes (zero warnings)
- [ ] `just typecheck` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No secrets, `.env` files, or `*.db` committed
- [ ] No `.bak` files committed (fileops backups are gitignored)

## Project Structure

```
src/aiwatcher_mcp/
  config.py          # pydantic-settings; all env vars live here
  database.py        # aiosqlite schema + CRUD
  ingestion.py       # RSS/Atom feed polling
  distillation.py    # Claude/Ollama scoring + digest generation
  alerting.py        # robofang + speechops TTS
  email_delivery.py  # email-mcp / SMTP dispatch
  scheduler.py       # APScheduler jobs
  api.py             # Starlette REST backend (:10946)
  server.py          # FastMCP 3.2 stdio server
```

## Environment Variables

See `.env.example` for the full list. Minimum for development:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Fleet Ports (do not conflict)

| Port  | Service              |
|-------|----------------------|
| 10946 | aiwatcher backend    |
| 10947 | aiwatcher frontend   |

Ports 3000, 5000, 5173, 8000, 8080 are fleet-forbidden.
