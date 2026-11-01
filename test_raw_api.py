import sys
sys.path.insert(0, '.')
from src.llm import _call_openai_compat
from src.config import get_settings
from scripts.analyze_codebase import CODE_EXTRACTION_PROMPT
from pathlib import Path

f = Path('E:/Desktop/homeassistant/homeassistant/backup_restore.py')
code = f.read_text(encoding='utf-8', errors='replace')
prompt = CODE_EXTRACTION_PROMPT.format(code=code[:4000])

cfg = get_settings()
print('Testing raw API response...')

# Direct call to see full response structure
import httpx
url = cfg.llm_base_url.rstrip("/") + "/v1/chat/completions"
headers = {"Authorization": f"Bearer {cfg.llm_api_key}", "Content-Type": "application/json"}
messages = [{"role": "system", "content": "You are a precise code analysis engine. Return valid JSON only."}, {"role": "user", "content": prompt}]
payload = {
    "model": cfg.llm_model,
    "messages": messages,
    "temperature": 0.1,
    "max_tokens": 2000,
    "response_format": {"type": "json_object"},
}
resp = httpx.post(url, headers=headers, json=payload, timeout=120)
print('STATUS:', resp.status_code)
data = resp.json()
print('FULL RESPONSE KEYS:', list(data.keys()))
if 'choices' in data:
    choice = data['choices'][0]
    print('CHOICE KEYS:', list(choice.keys()))
    msg = choice['message']
    print('MESSAGE KEYS:', list(msg.keys()))
    print('CONTENT:', repr(msg.get('content', '')[:300]))
    if 'reasoning_content' in msg:
        print('REASONING_CONTENT:', repr(msg.get('reasoning_content', '')[:300]))