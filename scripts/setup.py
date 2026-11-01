#!/usr/bin/env python3
"""One-command setup for the code-intelligence pipeline.
Usage: python scripts/setup.py
Checks: Neo4j graph exists? .env configured? Memory plugin ready?
Actions: use existing graph | build new graph | diagnose.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j import GraphDatabase
from src.config import get_settings
from src.memory_plugin import write_memory


def _check_neo4j():
    try:
        cfg = get_settings()
        driver = GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))
        with driver.session() as s:
            r = s.run("CALL dbms.components() YIELD name RETURN name AS n")
            name = r.single()["n"]
            r = s.run("MATCH (n:CodeEntity) RETURN count(n) AS c")
            count = r.single()["c"]
            r = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY c DESC LIMIT 5")
            rels = [(row["t"], row["c"]) for row in r]
        driver.close()
        return {"connected": True, "db": name, "code_entities": count, "relations": rels}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


def main():
    print("=== Code Intelligence Pipeline Setup ===")
    # 1. Check Neo4j
    stat = _check_neo4j()
    code_count = stat.get("code_entities", 0)
    rel_list = stat.get("relations", [])
    if stat.get("connected"):
        print(f"✓ Neo4j connected: {stat['db']}")
        print(f"  CodeEntity nodes: {code_count}")
        for rel, cnt in rel_list:
            print(f"  Relation {rel}: {cnt}")
    else:
        print(f"✗ Neo4j not connected: {stat.get('error', 'unknown')}")
    # 2. Check .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env_exists = env_path.exists()
    print(f"✓ .env file: {'found' if env_exists else 'MISSING'}")
    # 3. Check scripts/extractor
    extractor_path = Path(__file__).resolve().parent / "analyze_codebase.py"
    print(f"✓ Extractor: {'found' if extractor_path.exists() else 'MISSING'}")
    # 4. Check memory plugin
    plugin_path = Path(__file__).resolve().parent.parent / "src" / "memory_plugin.py"
    print(f"✓ Memory plugin: {'found' if plugin_path.exists() else 'MISSING'}")
    # 5. Ask user
    print("\n--- Setup Plan ---")
    print("Choose an action:")
    print("1) Use existing graph (continue with current Neo4j graph)")
    if code_count == 0:
        print("2) Build new graph from repo (extract + store + write MEMORY.md)")
    else:
        print("2) Rebuild/extend graph (re-run extraction on repo)")
    print("3) Just regenerate MEMORY.md from current graph")
    print("4) Diagnose (show config + connection details)")
    choice = input("Select (1-4): ").strip()
    # Execute
    if choice == "1":
        write_memory()
        print("✓ MEMORY.md regenerated from existing graph.")
    elif choice == "2" or choice == "3":
        root_path = input("Repo path (default: E:/Desktop/homeassistant/homeassistant): ").strip() or "E:/Desktop/homeassistant/homeassistant"
        root = Path(root_path)
        if not root.exists():
            print(f"✗ Path not found: {root}")
            return
        max_f = input("Max files for quick test? (default 5): ").strip()
        max_f = int(max_f) if max_f.isdigit() else 5
        # Run extraction
        import logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        from scripts.analyze_codebase import analyze_codebase
        stats = analyze_codebase(root, max_files=max_f)
        print(f"✓ Pilot complete: {stats}")
        # Write memory
        write_memory()
    elif choice == "4":
        stat = _check_neo4j()
        cfg = get_settings()
        print(f"LLM_PROVIDER={cfg.llm_provider}")
        print(f"LLM_MODEL={cfg.llm_model}")
        print(f"LLM_BASE_URL={cfg.llm_base_url}")
        print(f"LLM_API_KEY=redacted ({'set' if cfg.llm_api_key else 'MISSING'})")
        print(f"NEO4J_URI={cfg.neo4j_uri}")
        print(f"NEO4J_USER={cfg.neo4j_user}")
        print(f"NEO4J_PASSWORD=redacted ({'set' if cfg.neo4j_password else 'MISSING'})")
        print(f"NEO4J: connected={stat.get('connected')}, code_nodes={stat.get('code_entities', 0)}")
    else:
        print("No action selected.")

if __name__ == "__main__":
    main()
