"""Code graph extractor: analyzes Python files with Nemotron Ultra 550B via NVIDIA NIM."""

import logging
import sys
import hashlib
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import call_llm_structured
from src.graph import get_session
from src.db import get_driver, close

logger = logging.getLogger(__name__)

CODE_EXTRACTION_PROMPT = """You are a precise code analysis engine for Home Assistant (Python).
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
{{
  "entities": [
    {{"name": "async_backup", "type": "Function", "file_path": "backup_restore.py", "line_start": 1, "line_end": 1, "signature": "def async_backup(hass, data):", "docstring": ""}},
    {{"name": "BackupManager", "type": "Class", "file_path": "backup_restore.py", "line_start": 2, "line_end": 3, "signature": "class BackupManager:", "docstring": ""}}
  ],
  "relations": [
    {{"source": "backup_restore.py", "target": "async_backup", "type": "CONTAINS", "evidence_line": 1}},
    {{"source": "backup_restore.py", "target": "BackupManager", "type": "CONTAINS", "evidence_line": 2}}
  ]
}}

SOURCE CODE:
{code}

Return JSON:
{{
  "entities": [{{"name": "...", "type": "...", "file_path": "...", "line_start": 0, "line_end": 0, "signature": "...", "docstring": "..."}}],
  "relations": [{{"source": "...", "target": "...", "type": "...", "evidence_line": 0}}]
}}"""

@dataclass
class CodeEntity:
    name: str
    type: str
    file_path: str
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""

@dataclass
class CodeRelation:
    source: str
    target: str
    type: str
    evidence_chunk_id: str = ""
    evidence_line: int = 0

@dataclass
class CodeExtractionResult:
    file_path: str
    entities: list[CodeEntity] = field(default_factory=list)
    relations: list[CodeRelation] = field(default_factory=list)
    status: str = "pending"
    error_text: str = ""

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0] if "```" in text else text
    text = text.strip()
    # Robust JSON extraction for NIM structured-output mix-ups (reasoning_content etc.)
    # Find outermost JSON object between first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    # If it starts with {"entities", keep; else try to repair
    return text.strip()

def extract_from_file(file_path: Path, code: str) -> CodeExtractionResult:
    result = CodeExtractionResult(file_path=str(file_path), status="pending")
    prompt = CODE_EXTRACTION_PROMPT.format(code=code[:1000])  # Further reduced
    try:
        raw = call_llm_structured(
            prompt,
            system="You are a precise code analysis engine. Return valid JSON only.",
            use_cache=True,
            max_tokens=8000,
        )
        cleaned = _strip_fences(raw.text)
        import json
        data = json.loads(cleaned)
        if not isinstance(data, dict) or "entities" not in data or "relations" not in data:
            raise ValueError("Missing entities/relations keys")
        for e in data.get("entities", []):
            result.entities.append(CodeEntity(
                name=e.get("name", ""),
                type=e.get("type", ""),
                file_path=e.get("file_path", str(file_path)),
                line_start=e.get("line_start", 0),
                line_end=e.get("line_end", 0),
                signature=e.get("signature", ""),
                docstring=e.get("docstring", ""),
            ))
        for r in data.get("relations", []):
            result.relations.append(CodeRelation(
                source=r.get("source", ""),
                target=r.get("target", ""),
                type=r.get("type", ""),
                evidence_chunk_id=str(file_path),
                evidence_line=r.get("evidence_line", 0),
            ))
        result.status = "done"
        return result
    except Exception as exc:
        result.status = "failed"
        result.error_text = str(exc)
        logger.error("File %s FAILED: %s", file_path, exc)
        return result

def store_code_extraction(result: CodeExtractionResult) -> None:
    driver = get_driver()
    try:
        with driver.session() as s:
            # Store entities with unique id, name, entity_type
            entity_ids = {}
            for ent in result.entities:
                uid = hashlib.sha256(
                    f"{ent.file_path}:{ent.name}:{ent.type}:{ent.line_start}".encode()
                ).hexdigest()[:16]
                name = ent.name or ent.file_path or "unknown"
                entity_type = ent.type or "Unknown"
                entity_ids[name] = uid
                s.run(
                    "MERGE (e:CodeEntity {id: $id}) "
                    "SET e.name = $name, e.entity_type = $entity_type, e.type = $entity_type, "
                    "    e.file_path = $file_path, e.line_start = $line_start, "
                    "    e.line_end = $line_end, e.signature = $signature, e.docstring = $docstring",
                    id=uid,
                    name=name,
                    entity_type=entity_type,
                    file_path=ent.file_path,
                    line_start=ent.line_start,
                    line_end=ent.line_end,
                    signature=ent.signature,
                    docstring=ent.docstring,
                )
            # Store relations by matching entities via name (unique per file batch)
            for rel in result.relations:
                src_id = entity_ids.get(rel.source)
                tgt_id = entity_ids.get(rel.target)
                if not src_id or not tgt_id:
                    logger.warning("Skipping relation %s->%s: missing entity ids", rel.source, rel.target)
                    continue
                s.run(
                    "MATCH (a:CodeEntity {id: $src_id}) "
                    "MATCH (b:CodeEntity {id: $tgt_id}) "
                    "MERGE (a)-[r:CODE_REL {type: $type}]->(b) "
                    "SET r.evidence_line = $line, r.evidence_file = $file_path",
                    src_id=src_id,
                    tgt_id=tgt_id,
                    type=rel.type,
                    line=rel.evidence_line,
                    file_path=rel.evidence_chunk_id,
                )
        logger.info("Stored code extraction for %s (%d ent, %d rel)",
                    result.file_path, len(result.entities), len(result.relations))
    finally:
        close()

def analyze_codebase(root: Path, max_files: int | None = None) -> dict[str, Any]:
    py_files = list(root.rglob("*.py"))
    if max_files:
        py_files = py_files[:max_files]
    logger.info("Analyzing %d Python files under %s", len(py_files), root)

    stats = {"files": 0, "entities": 0, "relations": 0, "failed": 0}
    for f in py_files:
        code = f.read_text(encoding="utf-8", errors="replace")
        result = extract_from_file(f, code)
        if result.status == "done":
            store_code_extraction(result)
            stats["entities"] += len(result.entities)
            stats["relations"] += len(result.relations)
        else:
            stats["failed"] += 1
        stats["files"] += 1
        if stats["files"] % 10 == 0:
            logger.info("Progress: %d/%d files", stats["files"], len(py_files))
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = Path("E:/Desktop/homeassistant/homeassistant")
    stats = analyze_codebase(root, max_files=5)
    print("\n=== Analysis Complete ===")
    for k, v in stats.items():
        print(f"{k}: {v}")
