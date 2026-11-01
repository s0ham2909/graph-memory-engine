import sys
sys.path.insert(0, '.')
from src.llm import call_llm_structured
from scripts.analyze_codebase import CODE_EXTRACTION_PROMPT
from pathlib import Path

f = Path('E:/Desktop/homeassistant/homeassistant/backup_restore.py')
code = f.read_text(encoding='utf-8', errors='replace')
prompt = CODE_EXTRACTION_PROMPT.format(code=code[:4000])

print('Calling LLM...')
raw = call_llm_structured(
    prompt,
    system='You are a precise code analysis engine. Return valid JSON only.',
    use_cache=True,
    max_tokens=2000
)

text = raw.text
print('ORIGINAL:', repr(text[:500]))

def _strip_fences(text: str):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        text = text.rsplit('```', 1)[0] if '```' in text else text
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    return text.strip()

cleaned = _strip_fences(text)
print('CLEANED:', repr(cleaned[:500]))

import json
try:
    data = json.loads(cleaned)
    print('PARSED OK - entities:', len(data.get('entities', [])), 'relations:', len(data.get('relations', [])))
    for e in data.get('entities', []):
        print('  ', e.get('name'), e.get('type'))
except Exception as e:
    print('PARSE FAILED:', e)
    print('Full text:', text[:1000])