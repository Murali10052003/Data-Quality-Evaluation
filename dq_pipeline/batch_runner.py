"""
BatchDQRunner – memory-efficient chunked Pandas pipeline.

Instead of loading the entire business table into RAM, it streams rows in
configurable chunks.  Evaluations that work correctly on a subset of rows
(per-row checks) are run on each chunk and their counts are aggregated.
Evaluations that require the full dataset (cross-row checks like DupEval)
are flagged and still load the full table — they are reported separately.

Flow
────
1. Load active rules from dq_control
2. Split rules into CHUNK_COMPATIBLE and FULL_LOAD groups
3. Stream the table in batches of `batch_size` rows
   a. For each batch, run CHUNK_COMPATIBLE evals and accumulate counts
4. Load full table once for FULL_LOAD evals (with a logged warning)
5. Build aggregated result rows and persist to dq_results
"""

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dqeval.dataframe import DqEvalDataFrame
from results_collector import ResultsCollector

from .config import DBConfig
from .db import insert_dataframe, read_query, read_table, read_table_chunked
from .runner import DQRunner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Eval classification
# ---------------------------------------------------------------------------

# These evals check each row independently — correct results can be obtained
# by processing one chunk at a time and summing the failed/total counts.
CHUNK_COMPATIBLE = {
    "EmptyEval",
    "StringFormatEval",
    "RangeEval",
    "CategoricalValuesEval",
    "DataFreshnessEval",
    "DtypeEval",
    "CustomEval",
}

# These evals need visibility across *all* rows to be correct.
# e.g. a duplicate pair may span two different chunks.
FULL_LOAD_REQUIRED = {
    "DupEval",
    "UniqueEval",
    "StatisticalDistributionEval",
    "ReferentialIntegrityEval",
    "RowCountEval",
    "SchemaValidationEval",
}


class BatchDQRunner(DQRunner):
    """
    Memory-efficient variant of DQRunner that reads data in chunks.

    Parameters
    ----------
    engine:
        SQLAlchemy engine pointing at the target PostgreSQL database.
    config:
        DBConfig instance.
    batch_size:
        Number of rows per chunk (default 500 000).
    """

    def __init__(self, engine: Engine, config: DBConfig, batch_size: int = 500_000) -> None:
        super().__init__(engine, config)
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # Override run_table with batch-aware logic
    # ------------------------------------------------------------------

    def run_table(
        self,
        schema_name: str,
        table_name: str,
        rules: pd.DataFrame,
        run_id: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        logger.info(
            "→ [Batch] Evaluating %s.%s  (%d rule(s))  chunk_size=%d",
            schema_name, table_name, len(rules), self.batch_size,
        )

        # ── Classify rules ────────────────────────────────────────────
        def _get_eval_type(method: str) -> str:
            if method in CHUNK_COMPATIBLE:
                return "chunk"
            return "full"

        rules = rules.copy()
        rules["_eval_type"] = rules["dqmethod"].apply(_get_eval_type)

        chunk_rules = rules[rules["_eval_type"] == "chunk"].copy()
        full_rules  = rules[rules["_eval_type"] == "full"].copy()

        if not full_rules.empty:
            logger.warning(
                "  [Batch] %d rule(s) require full table load: %s",
                len(full_rules), full_rules["dqmethod"].tolist(),
            )

        # ── Shared config enrichment ───────────────────────────────────
        def _parse_enrich(row: pd.Series) -> dict:
            cfg = row["config"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            return self._enrich_config(row["dqmethod"], cfg, schema_name)

        control_cols = ["table_name", "dqmethod", "config"]

        # ── 1. Chunked processing for CHUNK_COMPATIBLE evals ──────────
        # Accumulator: key=(dqmethod, col_str) → {total, failed, ts, failed_records}
        accumulators: dict[tuple, dict] = {}

        if not chunk_rules.empty:
            chunk_slice = chunk_rules[control_cols].copy()
            chunk_slice["config"] = chunk_slice.apply(_parse_enrich, axis=1)

            chunk_num = 0
            for chunk_df in read_table_chunked(
                self.engine, schema_name, table_name, self.batch_size
            ):
                chunk_num += 1
                logger.debug("  [Batch] chunk %d  rows=%d", chunk_num, len(chunk_df))

                dqeval_chunk = DqEvalDataFrame(chunk_df)
                # Fresh collector per chunk so error_records don't bleed across chunks
                collector = ResultsCollector(dqeval_chunk, run_id=run_id)

                for _, rule_row in chunk_slice.iterrows():
                    dqmethod = rule_row["dqmethod"]
                    cfg      = rule_row["config"]
                    if isinstance(cfg, str):
                        cfg = json.loads(cfg)

                    col_str = collector._extract_column_info(cfg)
                    key = (dqmethod, col_str)

                    try:
                        # execute_eval returns the result row dict directly
                        row_result = collector.execute_eval(table_name, dqmethod, cfg)
                    except Exception as exc:
                        logger.warning("  [Batch] eval %s/%s failed on chunk %d: %s",
                                       dqmethod, col_str, chunk_num, exc)
                        continue

                    acc = accumulators.setdefault(key, {
                        "total": 0, "failed": 0, "run_timestamp": None,
                        "failed_records": [], "dqmethod": dqmethod, "col": col_str,
                    })
                    # dqevalcount in result row = failed count for this chunk
                    acc["failed"] += row_result.get("dqevalcount", 0)
                    acc["total"]  += len(chunk_df)
                    if acc["run_timestamp"] is None:
                        acc["run_timestamp"] = row_result.get("run_timestamp")

                    # Collect failed rows from this chunk
                    error_df = collector.get_error_records(
                        table=table_name, dqmethod=dqmethod, col=col_str
                    )
                    if error_df is not None and not error_df.empty:
                        for rec in json.loads(error_df.to_json(orient="records")):
                            acc["failed_records"].append({
                                "run_id":      run_id,
                                "schema_name": schema_name,
                                "table_name":  table_name,
                                "dqmethod":    dqmethod,
                                "col":         col_str,
                                "failed_row":  rec,
                            })

            logger.info("  [Batch] Processed %d chunk(s) for %s.%s", chunk_num, schema_name, table_name)

        # Build result rows from accumulators
        chunk_result_rows = []
        for (dqmethod, col_str), acc in accumulators.items():
            chunk_result_rows.append({
                "schema_name":   schema_name,
                "run_id":        run_id,
                "table_name":    table_name,
                "dqmethod":      dqmethod,
                "col":           col_str,
                "status":        "Failed" if acc["failed"] > 0 else "Success",
                "run_timestamp": acc["run_timestamp"],
                "dqevalcount":   acc["failed"],
            })

        chunk_results_df = pd.DataFrame(chunk_result_rows) if chunk_result_rows else pd.DataFrame()

        # ── 2. Full-load evals (DupEval, UniqueEval, etc.) ────────────
        full_results_df = pd.DataFrame()
        full_failed_records: list[dict] = []

        if not full_rules.empty:
            raw_df = read_table(self.engine, schema_name, table_name)
            dqeval_full = DqEvalDataFrame(raw_df)

            full_slice = full_rules[control_cols].copy()
            full_slice["config"] = full_slice.apply(_parse_enrich, axis=1)

            full_collector = ResultsCollector(dqeval_full, run_id=run_id)
            full_results_df = full_collector.run_control_table(full_slice)
            full_results_df.insert(0, "schema_name", schema_name)
            full_results_df = full_results_df.rename(columns={
                "table": "table_name", "dqevatcount": "dqevalcount",
            })

            for _, rule_row in full_slice.iterrows():
                dqmethod = rule_row["dqmethod"]
                cfg      = rule_row["config"]
                if isinstance(cfg, str):
                    cfg = json.loads(cfg)
                col_str = full_collector._extract_column_info(cfg)
                error_df = full_collector.get_error_records(
                    table=table_name, dqmethod=dqmethod, col=col_str
                )
                if error_df is None or error_df.empty:
                    continue
                for rec in json.loads(error_df.to_json(orient="records")):
                    full_failed_records.append({
                        "run_id": run_id, "schema_name": schema_name,
                        "table_name": table_name, "dqmethod": dqmethod,
                        "col": col_str, "failed_row": rec,
                    })

        # ── 3. Merge results ──────────────────────────────────────────
        parts = [df for df in [chunk_results_df, full_results_df] if not df.empty]
        results_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        # ── 4. Collect all failed records ─────────────────────────────
        all_failed: list[dict] = full_failed_records
        for acc in accumulators.values():
            all_failed.extend(acc["failed_records"])

        file_path = self._write_failed_log(run_id, table_name, all_failed)

        _empty = pd.DataFrame(
            columns=["run_id", "schema_name", "table_name", "failed_count", "file_path"]
        )
        failed_rows_df = (
            pd.DataFrame([{
                "run_id":       run_id,
                "schema_name":  schema_name,
                "table_name":   table_name,
                "failed_count": len(all_failed),
                "file_path":    file_path,
            }]) if all_failed else _empty
        )

        logger.info(
            "  ✓ [Batch] %s.%s → %d result(s), %d failed row(s)",
            schema_name, table_name, len(results_df), len(all_failed),
        )
        return results_df, failed_rows_df
