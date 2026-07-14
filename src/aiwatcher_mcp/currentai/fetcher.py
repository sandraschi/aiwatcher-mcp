"""Fetch Current AI os-ai-map dataset from GitHub raw YAML files."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import yaml

log = logging.getLogger(__name__)

_REPO_OWNER = "currentai-org"
_REPO_NAME = "os-ai-map"
_RAW_BASE = "https://raw.githubusercontent.com/{owner}/{repo}/{sha}"
_API_TREE = "https://api.github.com/repos/{owner}/{repo}/git/trees/{sha}?recursive=1"
_API_COMMIT = "https://api.github.com/repos/{owner}/{repo}/git/ref/heads/main"
_TIMEOUT = 30.0

_BUCKET_MAP = {
    "open_source": "open",
    "open_weights": "openish",
    "closed_api": "closed",
    "open_dataset": "open",
    "restricted": "closed",
}


def _openness_bucket(cls: str) -> str:
    return _BUCKET_MAP.get(cls, "openish")


async def fetch_normalized_products(
    commit_sha: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Fetch product + score + category YAML from GitHub. Returns (records, commit_sha)."""
    if commit_sha is None:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(_API_COMMIT.format(owner=_REPO_OWNER, repo=_REPO_NAME))
            r.raise_for_status()
            commit_sha = r.json()["object"]["sha"]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        tree_r = await client.get(
            _API_TREE.format(owner=_REPO_OWNER, repo=_REPO_NAME, sha=commit_sha)
        )
        tree_r.raise_for_status()
        tree = tree_r.json()

    product_paths: list[str] = []
    score_paths: list[str] = []
    category_paths: list[str] = []

    for entry in tree.get("tree", []):
        path = entry["path"]
        if entry["type"] != "blob" or not path.endswith(".yaml"):
            continue
        if path.startswith("sources/products/"):
            product_paths.append(path)
        elif path.startswith("sources/scores/"):
            score_paths.append(path)
        elif path.startswith("sources/categories/"):
            category_paths.append(path)

    log.info(
        "Found %d product, %d score, %d category YAMLs at %s",
        len(product_paths),
        len(score_paths),
        len(category_paths),
        commit_sha[:8],
    )

    async def _fetch_yaml(path: str) -> dict[str, Any]:
        url = f"{_RAW_BASE.format(owner=_REPO_OWNER, repo=_REPO_NAME, sha=commit_sha)}/{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as cl:
            resp = await cl.get(url)
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return yaml.safe_load(resp.text) or {}

    # Taxonomy
    tax = await _fetch_yaml("sources/taxonomy.yaml")
    cat_to_arc: dict[str, str] = {}
    for arc in tax.get("arcs", []):
        layer = arc.get("layer", "")
        for cat in arc.get("categories", []):
            cat_to_arc[cat] = layer

    # Category -> product slug mapping
    cat_product_map: dict[str, str] = {}
    for cpath in category_paths:
        cat_data = await _fetch_yaml(cpath)
        slug = cat_data.get("name", "")
        for prod_slug in cat_data.get("products", []):
            cat_product_map[prod_slug] = slug

    # Score data indexed by slug
    score_data: dict[str, dict[str, Any]] = {}
    for spath in score_paths:
        sc = await _fetch_yaml(spath)
        sslug = sc.get("product", "")
        if sslug:
            score_data[sslug] = sc

    # Products
    fetched_at = datetime.now(UTC).isoformat()
    short_commit = commit_sha[:8]
    records: list[dict[str, Any]] = []

    for ppath in product_paths:
        prod = await _fetch_yaml(ppath)
        slug = prod.get("name", "")
        if not slug:
            continue

        cat_name = cat_product_map.get(slug, "unknown")
        arc = cat_to_arc.get(cat_name, "unknown")
        score = score_data.get(slug, {})

        openness = score.get("openness", {}) or {}
        oc = openness.get("class", "")
        os_val = openness.get("score")

        adoption = score.get("adoption", {}) or {}
        al = adoption.get("level")

        capability = score.get("capability", {}) or {}
        cs = capability.get("score")

        records.append(
            {
                "product": prod.get("display_name", slug),
                "slug": slug,
                "type": prod.get("type", "unknown"),
                "category": cat_name,
                "stack_layer": f"{arc} / {cat_name}",
                "arc": arc,
                "openness_class": oc,
                "openness_bucket": _openness_bucket(oc),
                "openness_score": os_val,
                "maturity": os_val,
                "adoption_level": al,
                "capability_score": cs,
                "description": (prod.get("description") or "")[:500],
                "org": "",  # org data is in separate files, omitted for simplicity
                "source_commit": short_commit,
                "fetched_at": fetched_at,
            }
        )

    log.info("Normalized %d products from commit %s", len(records), short_commit)
    return records, commit_sha
