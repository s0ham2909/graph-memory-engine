import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.llm import call_llm_structured
from scripts.analyze_codebase import CODE_EXTRACTION_PROMPT

f = Path('E:/Desktop/homeassistant/homeassistant/backup_restore.py')
code = f.read_text(encoding='utf-8', errors='replace')
prompt = CODE_EXTRACTION_PROMPT.format(code=code[:4000])

raw = call_llm_structured(
    prompt,
    system='You are a precise code analysis engine. Return valid JSON only.',
    use_cache=False,
    max_tokens=4000
)
text = raw.text
print('ORIGINAL:', repr(text[:300]))

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
print('CLEANED:', repr(cleaned[:300]))
import json
try:
    data = json.loads(cleaned)
    print('PARSED OK - entities:', len(data.get('entities', [])), 'relations:', len(data.get('relations', [])))
except Exception as e:
    print('PARSE FAILED:', e)
    print('Full text length:', len(text))