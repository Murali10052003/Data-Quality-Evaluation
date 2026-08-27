"""
DQRunner – metadata-driven orchestrator.

Flow
────
1. Load active rules from dq_control
2. Group rules by (schema_name, table_name)
3. For each group
   a. Read the business table from PostgreSQL
   b. Wrap it in DqEvalDataFrame
   c. Pass the rule group to ResultsCollector.run_control_table()
   d. Collect the results DataFrame
4. Concatenate all results
5. Persist to dq_results

ResultsCollector is imported from the project root – do not modify it.
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

# ── ensure project root is on the path so results_collector.py is importable ──
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dqeval.dataframe import DqEvalDataFrame  # noqa: E402
from results_collector import ResultsCollector  # noqa: E402

from .config import DBConfig
from .db import insert_dataframe, read_query, read_table

logger = logging.getLogger(__name__)


class DQRunner:
    """Metadata-driven DQ execution pipeline.

    Parameters
    ----------
    engine:
        SQLAlchemy engine pointing at the target PostgreSQL database.
    config:
        :class:`DBConfig` instance that carries schema / table names.
    """

    def __init__(self, engine: Engine, config: DBConfig) -> None:
        self.engine = engine
        self.config = config

    # ------------------------------------------------------------------
    # Step 1 – load control rules
    # ------------------------------------------------------------------

    def load_active_rules(self) -> pd.DataFrame:
        """Return all rows from *dq_control* where ``is_active = TRUE``.

        Expected dq_control columns
        ───────────────────────────
        schema_name  TEXT        – schema that owns the business table
        table_name   TEXT        – business table to evaluate
        dqmethod     TEXT        – ResultsCollector eval key (e.g. "DupEval")
        config       TEXT/JSONB  – JSON config passed to the eval
        is_active    BOOLEAN     – only TRUE rows are processed
        """
        query = f"""
            SELECT
                schema_name,
                table_name,
                dqmethod,
                config
            FROM "{self.config.schema}"."{self.config.control_table}"
            WHERE is_active = TRUE
            ORDER BY schema_name, table_name, dqmethod
        """
        rules = read_query(self.engine, query)
        logger.info(
            "Loaded %d active rule(s) from %s.%s",
            len(rules),
            self.config.schema,
            self.config.control_table,
        )
        return rules

    # ------------------------------------------------------------------
    # Step 2 – evaluate a single table
    # ------------------------------------------------------------------

    def _enrich_config(self, dqmethod: str, cfg: dict, schema_name: str) -> dict:
        """Resolve non-JSON-serialisable values into config before eval.

        - CustomEval: evaluates a lambda string into an actual callable.
        - ReferentialIntegrityEval: loads the reference table from the DB
          when ``reference_df`` holds a table-name string.
        """
        if dqmethod == "CustomEval":
            func = cfg.get("func")
            if isinstance(func, str):
                resolved = eval(func)  # noqa: S307 – controlled internal config
                if not callable(resolved):
                    raise ValueError(
                        f"CustomEval: 'func' value '{func}' did not evaluate to a callable"
                    )
                cfg = {**cfg, "func": resolved}

        elif dqmethod == "ReferentialIntegrityEval":
            ref_value = cfg.get("reference_df")
            ref_schema = cfg.get("reference_schema", schema_name)
            if isinstance(ref_value, str):  # it's a table name, not yet a DataFrame
                logger.info(
                    "  Loading reference table %s.%s for ReferentialIntegrityEval",
                    ref_schema, ref_value,
                )

        elif dqmethod == "UnicodeValidationEval":
            # target_df in dq_control is stored as a table name string.
            # Load it from PostgreSQL here before the eval runs.
            tgt_value = cfg.get("target_df")
            tgt_schema = cfg.get("target_schema", schema_name)
            if isinstance(tgt_value, str):
                logger.info(
                    "  Loading target table %s.%s for UnicodeValidationEval",
                    tgt_schema, tgt_value,
                )
                cfg = {**cfg, "target_df": read_table(self.engine, tgt_schema, tgt_value)}

        return cfg

    def _write_failed_log(
        self, run_id: str, table_name: str, records: list[dict]
    ) -> str | None:
        """Write failing rows for one table to a JSON Lines (.jsonl) file.

        Each table gets its own file so schemas never mix:
        ``<failed_log_dir>/<run_id>/<table_name>.jsonl``.  One JSON object
        is written per line, which keeps the file streamable/appendable and
        avoids holding a giant JSON array in memory.

        Returns the path written, or ``None`` when there are no failing rows.
        """
        if not records:
            return None
        out_dir = os.path.join(self.config.failed_log_dir, run_id)
        os.makedirs(out_dir, exist_ok=True)
        file_path = os.path.join(out_dir, f"{table_name}.jsonl")
        with open(file_path, "w", encoding="utf-8") as fh:
            for rec in records:
                # default=str → serialise timestamps / Decimals safely
                fh.write(json.dumps(rec, default=str) + "\n")
        logger.info("  Wrote %d failed row(s) → %s", len(records), file_path)
        return file_path

    def run_table(
        self,
        schema_name: str,
        table_name: str,
        rules: pd.DataFrame,
        run_id: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Run DQ evaluations for one (schema_name, table_name) pair.

        Parameters
        ----------
        schema_name:
            PostgreSQL schema that owns the business table.
        table_name:
            Business table to evaluate.
        rules:
            Subset of the control table for this table (already filtered).
        run_id:
            Shared UUID for this pipeline execution, used to link
            dq_results rows to dq_failed_rows rows.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            (results_df, failed_rows_df) – summary results and the
            individual rows that failed each check.
        """
        logger.info(
            "→ Evaluating %s.%s  (%d rule(s))", schema_name, table_name, len(rules)
        )

        # Load the business table
        raw_df = read_table(self.engine, schema_name, table_name)
        logger.debug("  Loaded %d row(s) from %s.%s", len(raw_df), schema_name, table_name)

        # Wrap in DqEvalDataFrame
        dqeval_df = DqEvalDataFrame(raw_df)

        # Build the control slice expected by ResultsCollector
        # Columns: table_name, dqmethod, config
        control_slice = rules[["table_name", "dqmethod", "config"]].copy()

        def _parse_and_enrich(row: pd.Series) -> dict:
            cfg = row["config"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            return self._enrich_config(row["dqmethod"], cfg, schema_name)

        control_slice["config"] = control_slice.apply(_parse_and_enrich, axis=1)

        # Run all evals via ResultsCollector — share the pipeline run_id
        collector = ResultsCollector(dqeval_df, run_id=run_id)
        results_df: pd.DataFrame = collector.run_control_table(control_slice)

        # Enrich with schema name for downstream traceability
        results_df.insert(0, "schema_name", schema_name)

        # Align column names to match dq_results table schema
        results_df = results_df.rename(columns={
            "table": "table_name",
            "dqevatcount": "dqevalcount",
        })

        # ── Write failed rows to a per-table JSONL log file ──────────────
        # Instead of storing every failing row as one JSON blob in a DB cell,
        # we write one JSON object per line (JSON Lines) to a file named
        # after the table:  <failed_log_dir>/<run_id>/<table_name>.jsonl
        # A row that fails several checks appears once per check, tagged
        # with the dqmethod/col that flagged it.
        failed_records: list[dict] = []
        for _, rule_row in control_slice.iterrows():
            dqmethod = rule_row["dqmethod"]
            cfg = rule_row["config"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            col_str = collector._extract_column_info(cfg)
            error_df = collector.get_error_records(
                table=table_name, dqmethod=dqmethod, col=col_str
            )
            if error_df is None or error_df.empty:
                continue
            for row in json.loads(error_df.to_json(orient="records")):
                failed_records.append({
                    "run_id":      run_id,
                    "schema_name": schema_name,
                    "table_name":  table_name,
                    "dqmethod":    dqmethod,
                    "col":         col_str,
                    "failed_row":  row,
                })

        file_path = self._write_failed_log(run_id, table_name, failed_records)

        _empty_failed = pd.DataFrame(
            columns=["run_id", "schema_name", "table_name", "failed_count", "file_path"]
        )
        failed_rows_df = (
            pd.DataFrame([{
                "run_id":       run_id,
                "schema_name":  schema_name,
                "table_name":   table_name,
                "failed_count": len(failed_records),
                "file_path":    file_path,
            }])
            if failed_records else _empty_failed
        )

        logger.info(
            "  ✓ %s.%s  → %d result row(s), %d failed row(s)",
            schema_name, table_name, len(results_df), len(failed_records),
        )
        return results_df, failed_rows_df

    # ------------------------------------------------------------------
    # Step 3 – run all tables
    # ------------------------------------------------------------------

    def run_all(self) -> pd.DataFrame:
        """Execute DQ evaluations for every active rule, grouped by table.

        Returns
        -------
        pd.DataFrame
            Combined results from all tables, or an empty DataFrame if
            no rules are active / all evaluations failed.
        """
        rules = self.load_active_rules()

        if rules.empty:
            logger.warning(
                "No active rules found in %s.%s — nothing to run.",
                self.config.schema,
                self.config.control_table,
            )
            return pd.DataFrame(), pd.DataFrame()

        # Filter rules by schema/table if DQ_FILTER_SCHEMA / DQ_FILTER_TABLE are set
        filter_schema = os.environ.get("DQ_FILTER_SCHEMA", "")
        filter_table = os.environ.get("DQ_FILTER_TABLE", "")
        if filter_schema:
            rules = rules[rules["schema_name"] == filter_schema]
        if filter_table:
            rules = rules[rules["table_name"] == filter_table]

        if rules.empty:
            logger.warning(
                "No active rules match filter (schema=%s, table=%s) — nothing to run.",
                filter_schema or "*", filter_table or "*",
            )
            return pd.DataFrame(), pd.DataFrame()

        # Single run_id shared across every table so dq_results and
        # dq_failed_rows can be joined with a simple WHERE run_id = '…'
        run_id = os.environ.get("DQ_RUN_ID", str(uuid.uuid4()))
        logger.info("Pipeline run_id: %s", run_id)

        accumulated_results:  list[pd.DataFrame] = []
        accumulated_failed:   list[pd.DataFrame] = []

        for (schema_name, table_name), group in rules.groupby(
            ["schema_name", "table_name"], sort=False
        ):
            try:
                result_df, failed_df = self.run_table(
                    str(schema_name),
                    str(table_name),
                    group.reset_index(drop=True),
                    run_id=run_id,
                )
                accumulated_results.append(result_df)
                if not failed_df.empty:
                    accumulated_failed.append(failed_df)
            except Exception:
                logger.exception(
                    "Evaluation failed for %s.%s — skipping table.",
                    schema_name,
                    table_name,
                )

        if not accumulated_results:
            logger.error("All table evaluations failed. Nothing to persist.")
            return pd.DataFrame(), pd.DataFrame()

        combined_results = pd.concat(accumulated_results, ignore_index=True)
        combined_failed  = (
            pd.concat(accumulated_failed, ignore_index=True)
            if accumulated_failed
            else pd.DataFrame(
                columns=["run_id", "schema_name", "table_name", "failed_count", "file_path"]
            )
        )
        logger.info(
            "Pipeline complete. Total result rows: %d  |  Total failed row log(s): %d",
            len(combined_results), len(combined_failed),
        )
        return combined_results, combined_failed

    # ------------------------------------------------------------------
    # Step 4 – persist
    # ------------------------------------------------------------------

    def persist_results(self, results_df: pd.DataFrame) -> None:
        """Insert *results_df* into the configured ``dq_results`` table.

        The target table must already exist in PostgreSQL with columns
        that match the DataFrame.  ``to_sql`` appends rows by default.

        ``dq_results`` has a primary key on
        (run_id, schema_name, table_name, dqmethod, col). If the control
        table has more than one active rule with the same
        table/dqmethod/column combination (e.g. duplicate rules created
        via Rule Manager), ResultsCollector emits one result row per rule,
        which would otherwise violate the primary key. Drop those
        duplicates here, keeping the last result, so a duplicate rule
        never crashes the whole pipeline run.
        """
        key_cols = ["schema_name", "table_name", "dqmethod", "col"]
        if not results_df.empty and set(key_cols).issubset(results_df.columns):
            dupe_mask = results_df.duplicated(subset=key_cols, keep="last")
            if dupe_mask.any():
                logger.warning(
                    "Dropping %d duplicate result row(s) with the same %s "
                    "(likely duplicate active rules in dq_control): %s",
                    int(dupe_mask.sum()),
                    key_cols,
                    results_df.loc[dupe_mask, key_cols].to_dict(orient="records"),
                )
                results_df = results_df[~dupe_mask].reset_index(drop=True)

        insert_dataframe(
            engine=self.engine,
            df=results_df,
            schema=self.config.schema,
            table=self.config.results_table,
        )

    def persist_failed_rows(self, failed_rows_df: pd.DataFrame) -> None:
        """Log a summary of the per-table failed-row JSONL files.

        Failing rows are no longer stored in a database table.  Each table's
        failures are written to its own ``<run_id>/<table>.jsonl`` file during
        :meth:`run_table`; this method just reports what was written.
        """
        if failed_rows_df.empty:
            logger.info("No failed rows — no JSONL log files written.")
            return
        total = int(failed_rows_df["failed_count"].sum())
        logger.info(
            "Failed rows written to %d table log file(s), %d row(s) total.",
            len(failed_rows_df), total,
        )
        for _, row in failed_rows_df.iterrows():
            logger.info(
                "  • %s.%s → %d row(s) → %s",
                row["schema_name"], row["table_name"],
                row["failed_count"], row["file_path"],
            )

    # ------------------------------------------------------------------
    # Convenience: run + persist in one call
    # ------------------------------------------------------------------

    def execute(self) -> pd.DataFrame:
        """Run the full pipeline (evaluate → persist → return results)."""
        results, failed_rows = self.run_all()
        self.persist_results(results)
        self.persist_failed_rows(failed_rows)
        return results
