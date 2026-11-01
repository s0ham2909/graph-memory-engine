"""LLM wrapper with provider abstraction: gemini, openai_compat, none."""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass

from src.config import get_settings

logger = logging.getLogger(__name__)

_last_call_time: float = 0.0


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False


def _cache_path(prompt: str, model: str) -> Path:
    cfg = get_settings()
    cache_dir = Path(cfg.llm_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{model}::{prompt}".encode()).hexdigest()
    return cache_dir / f"{key}.json"


def _read_cache(path: Path) -> LLMResponse | None:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.debug("Cache hit: %s", path.name)
        return LLMResponse(
            text=data["response"],
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            cached=True,
        )
    return None


def _write_cache(path: Path, prompt: str, response: str, model: str,
                 pt: int, ct: int) -> None:
    path.write_text(
        json.dumps({
            "model": model,
            "prompt": prompt,
            "response": response,
            "prompt_tokens": pt,
            "completion_tokens": ct,
        }),
        encoding="utf-8",
    )


def _validate_keys(cfg: Any, provider: str) -> None:
    if provider == "gemini":
        key = cfg.gemini_api_key
        if not key or "your" in key.lower() or "placeholder" in key.lower():
            raise ValueError("GEMINI_API_KEY missing or placeholder. Set in .env")
    elif provider == "openai_compat":
        key = cfg.llm_api_key
        if not key or "your" in key.lower() or "placeholder" in key.lower():
            raise ValueError("LLM_API_KEY missing or placeholder for openai_compat")
    elif provider == "none":
        pass
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")


def _rate_limit(cfg: Any) -> None:
    global _last_call_time
    min_interval = 60.0 / cfg.llm_rpm if cfg.llm_rpm > 0 else 0.0
    elapsed = time.monotonic() - _last_call_time
    if elapsed < min_interval:
        sleep_for = min_interval - elapsed
        logger.debug("Rate limit: sleeping %.1fs", sleep_for)
        time.sleep(sleep_for)


def _retry(fn: Callable, *, max_retries: int = 4) -> Any:
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            is_429 = status == 429
            is_5xx = isinstance(status, int) and 500 <= status < 600
            if not (is_429 or is_5xx) or attempt == max_retries - 1:
                raise
            backoff = 2 ** attempt
            logger.warning("Retry %d/%d after %.1fs (status %s)", attempt + 1, max_retries, backoff, status)
            time.sleep(backoff)
    raise RuntimeError("Retries exhausted")


def _call_gemini(cfg: Any, prompt: str, system: str, temperature: float,
                 max_tokens: int, pydantic_model: Any) -> tuple[str, int, int]:
    from google import genai
    from google.genai import errors as genai_errors
    client = genai.Client(api_key=cfg.gemini_api_key)

    def _do_call() -> Any:
        _rate_limit(cfg)
        global _last_call_time
        _last_call_time = time.monotonic()

        if pydantic_model is not None:
            schema = _model_to_schema(pydantic_model)
            resp = client.models.generate_content(
                model=cfg.llm_model,
                contents=[system, prompt],
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            text = resp.text or "{}"
            # Detect quota/rate limit errors in response text (structured output may not raise)
            if "RESOURCE_EXHAUSTED" in text or "quota" in text.lower() or "rate limit" in text.lower():
                err = Exception(text)
                err.status_code = 429
                raise err
            pydantic_model.model_validate_json(text)
            return resp
        else:
            resp = client.models.generate_content(
                model=cfg.llm_model,
                contents=[system, prompt],
                config={"temperature": temperature, "max_output_tokens": max_tokens},
            )
            return resp

    resp = _retry(_do_call)
    text = resp.text or ""
    meta = getattr(resp, "usage_metadata", None)
    pt = getattr(meta, "prompt_token_count", None) or getattr(meta, "prompt_tokens", 0)
    ct = getattr(meta, "candidates_token_count", None) or getattr(meta, "completion_tokens", 0)
    return text, int(pt or 0), int(ct or 0)


def _call_openai_compat(cfg: Any, prompt: str, system: str, temperature: float,
                        max_tokens: int, pydantic_model: Any) -> tuple[str, int, int]:
    import httpx
    url = cfg.llm_base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.llm_api_key}", "Content-Type": "application/json"}

    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    if pydantic_model is not None:
        schema = _model_to_schema(pydantic_model)
        payload = {
            "model": cfg.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    else:
        payload = {
            "model": cfg.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def _do_call() -> Any:
        _rate_limit(cfg)
        global _last_call_time
        _last_call_time = time.monotonic()
        resp = httpx.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code >= 400:
            err = Exception(resp.text)
            err.status_code = resp.status_code
            raise err
        return resp.json()

    data = _retry(_do_call)
    text = data["choices"][0]["message"]["content"] or ""
    if not text:
        logger.warning("Empty response from API: %s", data)
    usage = data.get("usage", {})
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    if pydantic_model is not None:
        pydantic_model.model_validate_json(text)
    return text, pt, ct


def _model_to_schema(model: Any) -> dict:
    if not hasattr(model, "model_json_schema"):
        raise ValueError("pydantic_model must be a Pydantic BaseModel subclass")
    return model.model_json_schema()


def call_llm(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    temperature: float = 0.0,
    max_tokens: int = 2048,
    use_cache: bool = True,
) -> str:
    resp = call_llm_structured(
        prompt, system=system, temperature=temperature,
        max_tokens=max_tokens, use_cache=use_cache, pydantic_model=None,
    )
    return resp.text


def call_llm_structured(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    temperature: float = 0.0,
    max_tokens: int = 2048,
    use_cache: bool = True,
    pydantic_model: Any = None,
) -> LLMResponse:
    cfg = get_settings()
    provider = cfg.llm_provider
    model = cfg.llm_model

    _validate_keys(cfg, provider)

    cp = _cache_path(prompt, f"{provider}:{model}")
    if use_cache:
        cached = _read_cache(cp)
        if cached is not None:
            return cached

    if provider == "gemini":
        text, pt, ct = _call_gemini(cfg, prompt, system, temperature, max_tokens, pydantic_model)
    elif provider == "openai_compat":
        text, pt, ct = _call_openai_compat(cfg, prompt, system, temperature, max_tokens, pydantic_model)
    elif provider == "none":
        raise RuntimeError("LLM_PROVIDER=none -- no LLM calls allowed")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if use_cache:
        _write_cache(cp, prompt, text, f"{provider}:{model}", pt, ct)

    return LLMResponse(text=text, prompt_tokens=pt, completion_tokens=ct)
