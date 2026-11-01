#!/usr/bin/env python3
"""Test normal folder attach: reads HA source files, sends to LLM, measures tokens/latency."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import call_llm_structured

PROMPT = (
    "Describe backup_restore.py from the Home Assistant codebase. "
    "List its main classes, functions, decorators, and key imports. "
    "Be concise but complete."
)

def load_ha_files():
    """Load backup_restore.py and related HA files."""
    ha_root = Path("E:/Desktop/homeassistant/homeassistant")
    target_files = [
        "backup_restore.py",
        "bootstrap.py",
        "__init__.py",
    ]
    content = []
    for fname in target_files:
        fpath = ha_root / fname
        if fpath.exists():
            content.append(f"=== {fname} ===\n{fpath.read_text(encoding='utf-8', errors='replace')}")
        else:
            # search recursively
            matches = list(ha_root.rglob(fname))
            for m in matches[:1]:
                content.append(f"=== {m.relative_to(ha_root)} ===\n{m.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n".join(content)

def main():
    ha_code = load_ha_files()
    print(f"Loaded {len(ha_code)} chars from HA source")
    
    messages = [
        {"role": "system", "content": "You are a precise code analyst. Answer based only on provided source."},
        {"role": "user", "content": f"SOURCE CODE:\n{ha_code}\n\n{PROMPT}"}
    ]
    
    start = time.perf_counter()
    result = call_llm_structured(
        prompt=PROMPT,
        system="You are a precise code analyst. Answer based only on provided source.",
        use_cache=False,
        max_tokens=2000,
    )
    elapsed = time.perf_counter() - start
    
    # Extract token counts from response if available
    prompt_tokens = getattr(result, 'prompt_tokens', 'N/A')
    completion_tokens = getattr(result, 'completion_tokens', 'N/A')
    
    print(f"\n=== FOLDER ATTACH RESULT ===")
    print(f"Latency: {elapsed:.2f}s")
    print(f"Prompt tokens: {prompt_tokens}")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Answer:\n{result.text}")

if __name__ == "__main__":
    main()