import sys
sys.path.insert(0, '.')
from scripts.analyze_codebase import CODE_EXTRACTION_PROMPT
from pathlib import Path

f = Path('E:/Desktop/homeassistant/homeassistant/backup_restore.py')
code = f.read_text(encoding='utf-8', errors='replace')
prompt = CODE_EXTRACTION_PROMPT.format(code=code[:4000])
print('PROMPT LENGTH:', len(prompt))
print('PROMPT (first 200):', prompt[:200])
print('...')
print('PROMPT (last 200):', prompt[-200:])