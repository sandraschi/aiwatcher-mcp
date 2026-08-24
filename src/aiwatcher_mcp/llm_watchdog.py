"""
LLM Watchdog - Pre-flight LLM health check with auto-recovery and provider fallback.

Probes the configured LLM before critical operations (distillation, digest).
If the primary provider is down:
  1. Attempts auto-recovery (Ollama: pull + warm-up model)
  2. Falls back to alternative provider (ollama / lmstudio)
  3. Logs ERROR (not WARNING) when all recovery attempts fail
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

from aiwatcher_mcp.config import get_settings

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None

_OLLAMA_EXE = Path(r"C:\Users\sandr\AppData\Local\Programs\Ollama\ollama.exe")


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


def _resolve_base_url(provider: str, configured: str | None = None) -> str:
    if configured:
        return configured.rstrip("/")
    if provider == "ollama":
        return "http://localhost:11434/v1"
    if provider == "lmstudio":
        return "http://localhost:1234/v1"
    return "http://localhost:11434/v1"


async def _probe_chat(base_url: str, model: str) -> bool:
    """Minimal OpenAI-compatible chat probe - True if endpoint responds."""
    try:
        client = _get_client()
        resp = await client.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
            timeout=10.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


async def _recover_ollama(model: str, ollama_host: str = "http://localhost:11434") -> bool:
    """Pull model if missing, then warm up (load into GPU memory)."""
    client = _get_client()
    try:
        # Check if model exists
        tags_resp = await client.get(f"{ollama_host}/api/tags", timeout=10.0)
        if tags_resp.status_code != 200:
            return False
        installed = {m.get("name", "") for m in tags_resp.json().get("models", [])}
        # Match short name (e.g. "gemma4:e4b" from "gemma4:e4b" or "hf.co/...")
        model_short = model.split("/")[-1] if "/" in model else model
        exists = any(model_short in name or name == model for name in installed)

        if not exists:
            log.warning("Ollama model '%s' not installed - pulling...", model)
            proc = await asyncio.create_subprocess_exec(
                str(_OLLAMA_EXE),
                "pull",
                model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            if proc.returncode != 0:
                log.error("Ollama pull failed for '%s': %s", model, stderr.decode()[:500])
                return False
            log.info("Ollama pull succeeded for '%s'", model)

        # Warm-up: load model into memory, keep alive for 30min
        warm = await client.post(
            f"{ollama_host}/api/generate",
            json={"model": model, "prompt": "ping", "keep_alive": "30m", "stream": False},
            timeout=60.0,
        )
        if warm.status_code != 200:
            log.warning("Ollama warm-up returned %d for '%s'", warm.status_code, model)
            return False
        log.info("Ollama model '%s' loaded and warm", model)
        return True
    except TimeoutError:
        log.error("Ollama pull timed out for '%s'", model)
        return False
    except Exception as exc:
        log.warning("Ollama recovery failed for '%s': %s", model, exc)
        return False


async def ensure_llm_available(
    provider: str,
    model: str,
    base_url: str | None = None,
    *,
    attempt_recovery: bool = True,
) -> bool:
    """
    Ensure the configured LLM is reachable and the model is available.
    Returns True if the endpoint responds, False otherwise.
    When attempt_recovery=True, tries to pull/warm-up the model (Ollama).
    """
    cfg = get_settings()
    effective_url = _resolve_base_url(provider, base_url)

    # Quick probe
    if await _probe_chat(effective_url, model):
        return True

    if not attempt_recovery:
        return False

    log.warning("LLM '%s' unreachable at %s - attempting recovery...", provider, effective_url)

    recovered = False
    if provider == "ollama":
        ollama_host = effective_url.replace("/v1", "").replace("/v1/", "")
        recovered = await _recover_ollama(model, ollama_host)
    else:
        # LM Studio or unknown: retry with backoff (cannot auto-restart GUI app)
        for _attempt in range(cfg.llm_recovery_attempts):
            await asyncio.sleep(cfg.llm_recovery_cooldown_seconds)
            if await _probe_chat(effective_url, model):
                recovered = True
                break

    if recovered:
        log.info("LLM recovery succeeded: %s / %s", provider, model)
    else:
        log.error("LLM recovery FAILED: %s / %s at %s", provider, model, effective_url)

    return recovered


async def resolve_llm_chain(
    providers: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Try each provider in the chain; return the first working entry.
    Each entry: {'provider': str, 'model': str, 'base_url': str|None}
    If none respond after recovery attempts, returns None.
    Logs ERROR for each failed entry with detail.
    """
    cfg = get_settings()
    if providers is None:
        providers = []

        # Primary (configured provider)
        providers.append(
            {
                "provider": cfg.llm_provider,
                "model": cfg.distillation_model,
                "base_url": cfg.llm_base_url or None,
            }
        )

        # Fallback (if different from primary)
        fb_provider = cfg.llm_fallback_provider
        fb_model = cfg.llm_fallback_model
        if fb_provider.lower() != cfg.llm_provider.lower() or fb_model != cfg.distillation_model:
            providers.append(
                {
                    "provider": fb_provider,
                    "model": fb_model,
                    "base_url": cfg.llm_fallback_base_url or None,
                }
            )

    for entry in providers:
        prov = entry["provider"]
        model = entry["model"]
        url = entry.get("base_url")

        ok = await ensure_llm_available(prov, model, url)
        if ok:
            log.info("LLM resolved: %s / %s", prov, model)
            return entry

        log.error("LLM provider '%s/%s' FAILED - trying next", prov, model)

    log.critical("ALL LLM providers unreachable - distillation and digests disabled")
    return None


async def llm_health() -> dict[str, Any]:
    """
    Full LLM health check - probes primary provider, then fallback.
    Returns status dict suitable for /api/llm/health endpoint.
    """
    cfg = get_settings()
    primary_ok = await _probe_chat(
        _resolve_base_url(cfg.llm_provider, cfg.llm_base_url),
        cfg.distillation_model,
    )
    result: dict[str, Any] = {
        "provider": cfg.llm_provider,
        "model": cfg.distillation_model,
        "ok": primary_ok,
    }

    fb_provider = cfg.llm_fallback_provider
    fb_model = cfg.llm_fallback_model
    if fb_provider and fb_model:
        fallback_ok = await _probe_chat(
            _resolve_base_url(fb_provider, cfg.llm_fallback_base_url),
            fb_model,
        )
        result["fallback_provider"] = fb_provider
        result["fallback_model"] = fb_model
        result["fallback_ok"] = fallback_ok
        result["any_ok"] = primary_ok or fallback_ok
    else:
        result["any_ok"] = primary_ok

    return result
