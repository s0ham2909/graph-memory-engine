"""Verify Neo4j connectivity and report server info."""

import sys
import logging
from pathlib import Path

# Allow running as script from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_driver, close

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    driver = get_driver()
    try:
        info = driver.get_server_info()
        logger.info("Connected to Neo4j!")
        logger.info("  Address : %s", info.address)
        logger.info("  Agent   : %s", info.agent)
        logger.info("  Protocol: %s", info.protocol_version)
    except Exception as exc:
        logger.error("Connection failed: %s", exc)
        sys.exit(1)
    finally:
        close()


if __name__ == "__main__":
    main()
