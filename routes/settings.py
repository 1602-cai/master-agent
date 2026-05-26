"""LLM provider settings routes."""
from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from pathlib import Path

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from routes.deps import ROOT_DIR, job_runner

router = APIRouter()
log = logging.getLogger(__name__)

# ── Per-provider API key vault ──

_KEYS_FILE = ROOT_DIR / "data" / "provider_keys.json"


def _load_keys() -> dict:
    if _KEYS_FILE.exists():
        try:
            return json.loads(_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_keys(keys: dict):
    _KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEYS_FILE.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_key_for_provider(provider: str) -> str:
    return _load_keys().get(provider, "")


def _set_key_for_provider(provider: str, api_key: str):
    if not api_key:
        return
    keys = _load_keys()
    keys[provider] = api_key
    _save_keys(keys)


# ── Free model caches ──

_CACHE_TTL = 600
_openrouter_free_cache: list[str] = ["openrouter/free"]
_openrouter_cache_ts: float = 0
_zenmux_free_cache: list[str] = []
_zenmux_cache_ts: float = 0


def _is_free_openrouter(m: dict) -> bool:
    pricing = m.get("pricing", {})
    return str(pricing.get("prompt", "1")) == "0" and str(pricing.get("completion", "1")) == "0"


def _is_free_zenmux(m: dict) -> bool:
    pricings = m.get("pricings", {})
    for key in ("prompt", "completion"):
        items = pricings.get(key, [])
        if not items:
            return False
        if any(p.get("value", 1) != 0 for p in items):
            return False
    return True


async def _fetch_free_models(
    api_url: str,
    is_free_fn,
    cache: list[str],
    cache_ts: float,
    always_first: str | None = None,
) -> tuple[list[str], float]:
    now = _time.time()
    if now - cache_ts < _CACHE_TTL and len(cache) > 1:
        return cache, cache_ts
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        free_models: list[str] = []
        if always_first:
            free_models.append(always_first)
        for m in data:
            model_id = m.get("id", "")
            if model_id and model_id != always_first and is_free_fn(m):
                free_models.append(model_id)
        pinned = free_models[:1] if always_first else []
        rest = sorted(free_models[1:] if always_first else free_models)
        result = pinned + rest
        if result:
            cache = result
            cache_ts = now
        provider = api_url.split("//")[1].split("/")[0]
        log.info("Fetched %d free models from %s", len(result), provider)
    except Exception as e:
        log.warning("Failed to fetch models from %s: %s", api_url, e)
    return cache, cache_ts


async def _refresh_openrouter():
    global _openrouter_free_cache, _openrouter_cache_ts
    _openrouter_free_cache, _openrouter_cache_ts = await _fetch_free_models(
        "https://openrouter.ai/api/v1/models", _is_free_openrouter,
        _openrouter_free_cache, _openrouter_cache_ts, "openrouter/free",
    )


async def _refresh_zenmux():
    global _zenmux_free_cache, _zenmux_cache_ts
    _zenmux_free_cache, _zenmux_cache_ts = await _fetch_free_models(
        "https://zenmux.ai/api/v1/models", _is_free_zenmux,
        _zenmux_free_cache, _zenmux_cache_ts, None,
    )


def _get_providers_sync() -> dict:
    return {
        "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com", "models": ["deepseek-chat", "deepseek-reasoner"]},
        "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "models": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini", "o3-mini"]},
        "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "models": list(_openrouter_free_cache)},
        "zenmux": {"name": "ZenMux", "base_url": "https://zenmux.ai/api/v1", "models": list(_zenmux_free_cache)},
        "qwen": {"name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "models": ["qwen-plus", "qwen-turbo", "qwen-max"]},
        "zhipu": {"name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "models": ["glm-4-plus", "glm-4", "glm-4-flash"]},
        "custom": {"name": "自定义", "base_url": "", "models": []},
    }


# ── Routes ──

@router.get("/api/settings/llm")
async def get_llm_settings():
    """Get current LLM provider settings."""
    import skills.ppt_master.config as cfg
    await asyncio.gather(_refresh_openrouter(), _refresh_zenmux())
    providers = _get_providers_sync()
    current_provider = "custom"
    for pid, pinfo in providers.items():
        if pinfo["base_url"] and pinfo["base_url"] in cfg._base_url:
            current_provider = pid
            break
    api_key = cfg._api_key
    saved_keys = _load_keys()
    provider_key_status = {pid: bool(saved_keys.get(pid)) for pid in providers}
    return JSONResponse({
        "provider": current_provider,
        "base_url": cfg._base_url,
        "model": cfg._model_name,
        "api_key_set": bool(api_key),
        "api_key_preview": (api_key[:8] + "..." + api_key[-4:]) if len(api_key) > 12 else ("***" if api_key else ""),
        "providers": providers,
        "provider_key_status": provider_key_status,
    })


@router.get("/api/settings/llm/key/{provider_id}")
async def get_provider_key_preview(provider_id: str):
    """Get saved API key preview for a specific provider."""
    key = _get_key_for_provider(provider_id)
    return JSONResponse({
        "provider": provider_id,
        "api_key_set": bool(key),
        "api_key_preview": (key[:8] + "..." + key[-4:]) if len(key) > 12 else ("***" if key else ""),
    })


@router.put("/api/settings/llm")
async def update_llm_settings(payload: dict):
    """Update LLM provider settings and hot-reload."""
    active_jobs = []
    try:
        active_jobs = job_runner().active_job_ids()
    except Exception:
        active_jobs = []
    if active_jobs:
        return JSONResponse({
            "error": "当前有任务正在运行，不能热切换模型配置。请等待任务完成或取消后再修改。",
            "active_jobs": active_jobs,
        }, status_code=409)

    provider = payload.get("provider", "")
    api_key = payload.get("api_key", "")
    base_url = payload.get("base_url", "")
    model = payload.get("model", "")

    providers = _get_providers_sync()
    if provider in providers and provider != "custom":
        if not base_url:
            base_url = providers[provider]["base_url"]
        if not model and providers[provider]["models"]:
            model = providers[provider]["models"][0]

    if api_key and provider:
        _set_key_for_provider(provider, api_key)

    if not api_key and provider:
        api_key = _get_key_for_provider(provider)

    if not api_key and not base_url:
        return JSONResponse({"error": "需要提供 API Key 或 Base URL"}, status_code=400)

    # Write to .env
    env_path = ROOT_DIR / ".env"
    env_lines = []
    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").strip().split("\n")
    env_lines = [
        l for l in env_lines
        if not l.strip().startswith(("DEEPSEEK_API_KEY=", "DEEPSEEK_BASE_URL=", "DEEPSEEK_MODEL=",
                                      "OPENAI_API_KEY=", "OPENAI_BASE_URL=", "OPENAI_MODEL="))
    ]
    if api_key:
        env_lines.append(f"DEEPSEEK_API_KEY={api_key}")
    if base_url:
        env_lines.append(f"DEEPSEEK_BASE_URL={base_url}")
    if model:
        env_lines.append(f"DEEPSEEK_MODEL={model}")
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # Hot-reload
    try:
        import skills.ppt_master.config as cfg
        from openai import AsyncOpenAI
        from agents import OpenAIChatCompletionsModel

        cfg._api_key = api_key or cfg._api_key
        cfg._base_url = base_url or cfg._base_url
        cfg._model_name = model or cfg._model_name
        cfg._client = AsyncOpenAI(base_url=cfg._base_url, api_key=cfg._api_key, timeout=180.0, max_retries=3)
        cfg.MODEL = OpenAIChatCompletionsModel(model=cfg._model_name, openai_client=cfg._client)

        import skills.ppt_master.agents as agents_mod
        for attr_name in dir(agents_mod):
            obj = getattr(agents_mod, attr_name)
            if hasattr(obj, 'model') and hasattr(obj, 'name'):
                try:
                    obj.model = cfg.MODEL
                except Exception:
                    pass
        log.info("LLM config reloaded: provider=%s model=%s base_url=%s", provider, cfg._model_name, cfg._base_url)
    except Exception as e:
        log.error("Failed to reload LLM config: %s", e)
        return JSONResponse({"error": f"配置已保存但热重载失败: {e}"}, status_code=500)

    return JSONResponse({
        "status": "ok",
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key_set": bool(api_key),
    })


@router.get("/api/health")
async def health():
    return JSONResponse({"status": "ok"})
