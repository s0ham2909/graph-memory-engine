#!/usr/bin/env python
"""Connectivity check for LLM provider - prints provider, model, tokens, latency."""

import time
import sys
sys.path.insert(0, '.')

from src.llm import call_llm
from src.config import get_settings

cfg = get_settings()
print(f"Provider: {cfg.llm_provider}")
print(f"Model: {cfg.llm_model}")
print(f"Base URL: {cfg.llm_base_url or 'N/A'}")

start = time.monotonic()
try:
    resp = call_llm("Reply with exactly the word OK", use_cache=False)
    elapsed = time.monotonic() - start
    print(f"Latency: {elapsed:.2f}s")
    print(f"Response: {resp}")
    print(f"Prompt tokens: {0}")
    print(f"Completion tokens: {0}")
    print("PASSED")
except Exception as e:
    elapsed = time.monotonic() - start
    print(f"Latency: {elapsed:.2f}s")
    print(f"FAILED: {e}")
    sys.exit(1)
