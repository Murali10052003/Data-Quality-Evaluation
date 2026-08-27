"""
main.py – DQ pipeline entry point (Pandas, chunked).

Usage
─────
    python main.py                        # default 500 000 rows per chunk
    DQ_BATCH_SIZE=1000000 python main.py  # 1 M rows per chunk

The script will:
  1. Connect to PostgreSQL
  2. Read active rules from dq_control
  3. For each (schema, table) group:
       • Per-row evals  → streamed in chunks of DQ_BATCH_SIZE rows
       • Cross-row evals (DupEval, UniqueEval, …) → full table load
  4. Insert the combined results into dq_results
  5. Print a summary to stdout
"""

import logging
import os
import sys

from dq_pipeline.config import DBConfig
from dq_pipeline.db import get_engine
from dq_pipeline.batch_runner import BatchDQRunner


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Run the chunked Pandas DQ pipeline. Returns 0 on success, 1 on failure."""
    config     = DBConfig()
    batch_size = int(os.environ.get("DQ_BATCH_SIZE", "500000"))
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    logger.info("DQ pipeline starting (Pandas batch, chunk=%d) …  config=%s", batch_size, config)

    try:
        engine = get_engine(config)
        runner = BatchDQRunner(engine, config, batch_size=batch_size)
        results = runner.execute()          # evaluate + persist
    except Exception:
        logger.exception("Pipeline failed with an unhandled exception.")
        return 1

    if results.empty:
        logger.warning("Pipeline produced no results.")
        return 1

    # ── summary ──────────────────────────────────────────────────────────
    total   = len(results)
    passed  = (results["status"] == "Success").sum()
    failed  = (results["status"] == "Failed").sum()
    errors  = (results["status"] == "Error").sum()

    logger.info(
        "Summary → total=%d  passed=%d  failed=%d  errors=%d",
        total, passed, failed, errors,
    )

  

    

    return 0


if __name__ == "__main__":
    sys.exit(main())
