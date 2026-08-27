"""
load_failed_logs.py — turn per-table failed-row JSONL logs into analysis tables.

The DQ pipeline writes failing rows to one JSON Lines file per table:

    failed_logs/<run_id>/<table_name>.jsonl

This utility reads those files and appends the rows into a per-table
PostgreSQL table named ``<table_name>_failed_rows`` (auto-created on first
load), flattening each record into columns plus the run metadata.

Usage
─────
    # load the most recent run
    python load_failed_logs.py

    # load a specific run
    python load_failed_logs.py --run-id 3f2a9c1e-....

    # point at a different log directory / DB schema
    python load_failed_logs.py --failed-log-dir /data/failed_logs

DB connection is read from the same environment variables the pipeline uses
(DQ_DB_HOST, DQ_DB_PORT, DQ_DB_NAME, DQ_DB_USER, DQ_DB_PASSWORD, DQ_DB_SCHEMA).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys

import pandas as pd

from dq_pipeline.config import DBConfig
from dq_pipeline.db import get_engine, insert_dataframe

logger = logging.getLogger("load_failed_logs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten(rec: dict) -> dict:
    """Explode one JSONL record into a flat row: metadata + the failing row."""
    row = dict(rec.get("failed_row", {}))
    return {
        "run_id":   rec.get("run_id"),
        "dqmethod": rec.get("dqmethod"),
        "col":      rec.get("col"),
        **row,
    }


def _latest_run_dir(base_dir: str) -> str | None:
    """Return the most recently modified <run_id> sub-folder, or None."""
    if not os.path.isdir(base_dir):
        return None
    subdirs = [
        os.path.join(base_dir, d)
        for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d))
    ]
    if not subdirs:
        return None
    return max(subdirs, key=os.path.getmtime)


def load_file(
    engine,
    schema: str,
    path: str,
    chunk_size: int = 50_000,
) -> int:
    """Load a single ``<table>.jsonl`` file into ``<table>_failed_rows``.

    Reads the file line by line and inserts in batches of *chunk_size* so
    even very large log files never fully materialise in memory. Returns the
    number of rows loaded.
    """
    table_name = os.path.splitext(os.path.basename(path))[0]
    target = f"{table_name}_failed_rows"

    buffer: list[dict] = []
    loaded = 0

    def _flush() -> None:
        nonlocal buffer, loaded
        if not buffer:
            return
        insert_dataframe(engine, pd.DataFrame(buffer), schema=schema, table=target)
        loaded += len(buffer)
        buffer = []

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            buffer.append(_flatten(json.loads(line)))
            if len(buffer) >= chunk_size:
                _flush()
    _flush()

    logger.info("Loaded %d row(s) from %s → %s.%s", loaded, path, schema, target)
    return loaded


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    config = DBConfig()

    parser = argparse.ArgumentParser(description="Load failed-row JSONL logs into tables.")
    parser.add_argument(
        "--run-id",
        help="Run id sub-folder to load. Defaults to the most recent run.",
    )
    parser.add_argument(
        "--failed-log-dir",
        default=config.failed_log_dir,
        help=f"Base directory of the JSONL logs (default: {config.failed_log_dir}).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50_000,
        help="Rows per insert batch (default: 50000).",
    )
    args = parser.parse_args()

    # Resolve which run folder to load
    if args.run_id:
        run_dir = os.path.join(args.failed_log_dir, args.run_id)
    else:
        run_dir = _latest_run_dir(args.failed_log_dir)

    if not run_dir or not os.path.isdir(run_dir):
        logger.error("No log folder found under %s (run-id=%s).", args.failed_log_dir, args.run_id)
        return 1

    files = sorted(glob.glob(os.path.join(run_dir, "*.jsonl")))
    if not files:
        logger.warning("No .jsonl files found in %s — nothing to load.", run_dir)
        return 0

    logger.info("Loading %d file(s) from %s", len(files), run_dir)

    engine = get_engine(config)
    total = 0
    for path in files:
        try:
            total += load_file(engine, config.schema, path, chunk_size=args.chunk_size)
        except Exception:
            logger.exception("Failed to load %s — skipping.", path)

    logger.info("Done. Loaded %d row(s) total from %s.", total, run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
