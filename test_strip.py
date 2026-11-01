import sys
sys.path.insert(0, '.')
from src.llm import call_llm_structured

raw = call_llm_structured(
    'Return JSON: {"entities": [{"name": "test", "type": "Function", "file_path": "test.py", "line_start": 1, "line_end": 1, "signature": "def test():", "docstring": ""}], "relations": []}',
    system='Return valid JSON only.',
    use_cache=False,
    max_tokens=200
)

text = raw.text
print('ORIGINAL:', repr(text[:200]))

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
print('CLEANED:', repr(cleaned[:200]))

import json
data = json.loads(cleaned)
print('PARSED OK - entities:', len(data.get('entities', [])), 'relations:', len(data.get('relations', [])))