"""
Entrypoint: python main.py
"""

import asyncio
import logging

from run import main as run_main


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(run_main())
