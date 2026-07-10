# Current AI "OS AI Map" — Recon Report

**Date**: 2026-07-05  
**Source**: https://github.com/currentai-org/os-ai-map  
**Repo status**: Active — multiple commits per day

## Data Architecture

The upstream repo organises data as a tree of YAML files under `sources/`:

```
sources/
├── taxonomy.yaml          # Arc → layer → categories mapping
├── categories/*.yaml      # Category definitions with product membership
├── organizations/*.yaml   # Org definitions with product membership
├── products/*.yaml        # Product metadata (name, display_name, github repos)
└── scores/*.yaml          # Openness/adoption/capability scores per product
```

A build script (`warehouse/ingest/build_stack_map.py`) merges all YAML into a single
flat CSV: `warehouse/catalog/stack_map/repos.csv`.

## Chosen Source File

**`warehouse/catalog/stack_map/repos.csv`** — compiled CSV with all scored products linked
to GitHub repos.

### Schema (CSV columns)

| Column | Type | Description | Maps to internal |
|--------|------|-------------|------------------|
| `repo` | str | GitHub org/repo (lowercase) | (discard) |
| `product_slug` | str | Machine-readable product name | `product` |
| `product_name` | str | Display name | (discard) |
| `org` | str | Organization display name | (discard) |
| `category` | str | Fine-grained category slug (e.g. `base_pretrained`, `orchestration_agents`) | (discard) |
| `layer` | str | Columbia ontology layer: `product_ux`, `model_components`, `infrastructure` | `stack_layer` |
| `openness_class` | str | `open_source`, `open_weights`, `open_core`, `source_available`, `gated`, `unknown` | `openness_class` |
| `openness_bucket` | str | Coarse bucket: `open`, `open-ish`, `closed` | (derived) |
| `adoption` | int or "" | Adoption level 1-5 (from `sources/scores/*.yaml` adoption.level) | `adoption_level` |
| `capability` | int or "" | Capability score 1-5 (from scores) | (discard) |
| `maturity` | float or "" | Weighted maturity score (adoption × capability blend) | `maturity_stage` |

### Key fields for our purposes

- `layer` — the three arcs of the stack (product_ux, model_components, infrastructure).  
  These are the Columbia/GPAIS openness ontology layers.
- `openness_class` — granular openness category (open_source, open_weights, open_core, etc.)
- `openness_bucket` — coarse grouping: `open`, `open-ish`, `closed`
- `adoption` — 1-5 adoption level (usage volume, user reach)
- `maturity` — composite weighted score

### Data rows

~500-600 scored products as of July 2026. All machine-readable YAML/CSV. No parquet dependency.

## Commit Cadence

Last 10 commits (as of 2026-07-04):

| Date | Author | Type | Message |
|------|--------|------|---------|
| 2026-07-04 22:30 | bot | chore | Regenerate notebook data |
| 2026-07-04 22:29 | Carl Cervone | feat | Dataset provenance sweep + lineage capture (#84) |
| 2026-07-04 22:25 | bot | chore | Regenerate notebook data |
| 2026-07-04 22:24 | Carl Cervone | feat | Recalibrate dataset maturity + disclosure gap (#83) |
| 2026-07-03 18:47 | bot | chore | Regenerate notebook data |
| 2026-07-03 18:46 | Carl Cervone | feat | Add Ornith 1.0 9B (#82) |
| 2026-07-03 18:40 | bot | chore | Regenerate notebook data |
| 2026-07-03 18:39 | Carl Cervone | chore | Merge zhipu-ai org (#81) |
| 2026-07-03 18:34 | bot | chore | Regenerate notebook data |
| 2026-07-03 18:34 | Carl Cervone | feat | Refresh GLM-5.2 adoption (#80) |

**Pattern**: Bot regenerates CSV after every human commit. Human commits average 1-3/day.
The CSV is always in sync with the YAML source of truth.

## Recommended Refresh Interval

**24 hours** — matches the daily bot regeneration cycle. The CSV is rebuilt by CI on every
push; a 24h poll cadence avoids hitting the raw.githubusercontent.com CDN on every bot
commit (which triggers 2x per human commit due to the bot's own regeneration).

## Fetch Strategy

1. Call `GET https://api.github.com/repos/currentai-org/os-ai-map/commits/main?per_page=1`
   to get latest commit SHA (no auth required for public repo).
2. Fetch CSV from `https://raw.githubusercontent.com/currentai-org/os-ai-map/{sha}/warehouse/catalog/stack_map/repos.csv`
3. Parse CSV into internal JSON schema. Each row becomes:
   ```json
   {
     "product": "aider",
     "stack_layer": "product_ux",
     "openness_class": "open_source",
     "maturity_stage": 2.5,
     "adoption_level": 3,
     "source_commit": "609f322479...",
     "fetched_at": "2026-07-05T12:00:00Z"
   }
   ```

## Verdict

Machine-readable, well-maintained, no blockers. Proceed with implementation.
