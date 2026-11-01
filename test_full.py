import sys
sys.path.insert(0, '.')
from src.llm import call_llm_structured

prompt = """You are a precise code analysis engine for Home Assistant (Python).
Given the SOURCE CODE below, extract code entities and relationships.

Allowed entity types: File, Class, Function, Method, Import, Decorator, ConfigSchema, Service, Entity, Automation, Constant.
Allowed relation types: CONTAINS, DEFINES, INHERITS, IMPORTS, CALLS, DECORATES, HAS_CONFIG, PROVIDES_SERVICE, REGISTERS_ENTITY, TRIGGERS_AUTOMATION, USES_CONSTANT.

Rules:
- Only extract facts explicitly present in the code.
- Use canonical names (full module path for classes/functions).
- For imports, include the imported module and what symbols are imported.
- For Home Assistant specifics: detect @callback, @property, @classmethod, @staticmethod; detect async def; detect CONFIG_SCHEMA; detect SERVICE_SCHEMA; detect ENTITY_ID_FORMAT; detect automation triggers.
- Return ONLY valid JSON matching the schema (no markdown, no explanation).

EXAMPLE:
SOURCE CODE:
def async_backup(hass, data):
    pass
class BackupManager:
    def __init__(self): pass

Return JSON:
{
  "entities": [
    {"name": "async_backup", "type": "Function", "file_path": "backup_restore.py", "line_start": 1, "line_end": 1, "signature": "def async_backup(hass, data):", "docstring": ""},
    {"name": "BackupManager", "type": "Class", "file_path": "backup_restore.py", "line_start": 2, "line_end": 3, "signature": "class BackupManager:", "docstring": ""}
  ],
  "relations": [
    {"source": "backup_restore.py", "target": "async_backup", "type": "CONTAINS", "evidence_line": 1},
    {"source": "backup_restore.py", "target": "BackupManager", "type": "CONTAINS", "evidence_line": 2}
  ]
}

SOURCE CODE:
# Backup and restore functionality
import logging
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

async def async_backup(hass, data):
    pass

Return JSON:
{
  "entities": [{"name": "...", "type": "...", "file_path": "...", "line_start": 0, "line_end": 0, "signature": "...", "docstring": "..."}],
  "relations": [{"source": "...", "target": "...", "type": "...", "evidence_line": 0}]
}"""

raw = call_llm_structured(
    prompt,
    system='You are a precise code analysis engine. Return valid JSON only.',
    use_cache=False,
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
data = json.loads(cleaned)
print('PARSED OK - entities:', len(data.get('entities', [])), 'relations:', len(data.get('relations', [])))
for e in data.get('entities', []):
    print('  ', e.get('name'), e.get('type'))