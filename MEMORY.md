# Project Memory: Home Assistant Core

Auto-generated from Neo4j knowledge graph. Updated on import.

## Modules

- **__init__.py** — Init file for Home Assistant.
- **backup_restore.py** — Home Assistant module to handle restoring backups.
- **bootstrap.py** — Provide methods to bootstrap a Home Assistant instance.
- **serial_exclusivity.py** — Block shared access to serial ports by forcing pyserial exclusivity.

Also wires up the `pySerial` logger around port opens, since pyserial itself is silent.

## Key Classes

- **RestoreBackupFileContent** (`backup_restore.py`): @dataclass
class RestoreBackupFileContent: — Definition for restore backup file content.

## Decorators & Config Schemas

- **@wraps(_original_platform_open)** — No docstring
- **@wraps(_original_socket_open)** — No docstring

## Relationship Summary

- **CONTAINS**: 40
- **IMPORTS**: 20
- **DECORATES**: 3

## Ingested Documents (Vector RAG)

- **session:20261012_194239_70c37b**: 139 chunks, ~0 tokens
- **session:20261026_210619_35bda0**: 79 chunks, ~0 tokens

---
*End of memory export*