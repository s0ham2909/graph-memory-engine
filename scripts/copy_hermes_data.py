"""Copy Hermes memory files and a consistent snapshot of state.db for KGIRS."""
import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path


def default_src() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    local = os.environ.get("LOCALAPPDATA")
    if local and (Path(local) / "hermes").exists():
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path, default=default_src())
    p.add_argument("--dst", type=Path, default=Path("data/raw/hermes"))
    a = p.parse_args()
    src, dst = a.src.expanduser(), a.dst

    print(f"Source:      {src}")
    print(f"Destination: {dst.resolve()}")
    if not src.exists():
        sys.exit(f"ERROR: source folder not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    # 1. memory files
    for name in ("MEMORY.md", "USER.md"):
        f = src / "memories" / name
        if f.exists():
            shutil.copy2(f, dst / name)
            print(f"copied {name} ({f.stat().st_size} bytes)")
        else:
            print(f"MISSING {name} (Hermes may not have saved memory yet)")

    # 2. database: copy file + WAL companions, then merge into one file
    db = src / "state.db"
    if not db.exists():
        sys.exit("ERROR: state.db not found. Run some Hermes sessions first.")
    out = dst / "state_copy.db"
    for suffix in ("", "-wal", "-shm"):
        original = Path(str(db) + suffix)
        target = Path(str(out) + suffix)
        if target.exists():
            target.unlink()
        if original.exists():
            shutil.copy2(original, target)
            print(f"copied state.db{suffix} ({original.stat().st_size} bytes)")

    con = sqlite3.connect(out)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("PRAGMA journal_mode=DELETE")
    print("\nTables in the copy:")
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        try:
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            print(f"  {t}: {n} rows")
        except sqlite3.Error as e:
            print(f"  {t}: (could not count: {e})")
    con.close()
    print("\nDone. The copy is safe to read; your live Hermes files were not modified.")


if __name__ == "__main__":
    main()