"""
compare_tables.py
-----------------
Reads source and target tables from PostgreSQL, runs Unicode validation,
and prints results in a clean table format.

Configuration (edit the CONFIG block below)
-------------------------------------------
  SOURCE_TABLE   : table that arrived from the ETL pipeline
  TARGET_TABLE   : clean reference table
  KEY_COLUMN     : column used to match rows between the two tables
  COLUMNS        : list of text columns to validate
  SCHEMA         : PostgreSQL schema (default: public)

DB connection is read from environment variables (or a .env file):
  DQ_DB_HOST, DQ_DB_PORT, DQ_DB_NAME, DQ_DB_USER, DQ_DB_PASSWORD


"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dq_pipeline.config import DBConfig
from dq_pipeline.db import get_engine, read_table
from dqeval.dataframe import DqEvalDataFrame
from dqeval.evals.unicode_validation_eval import UnicodeValidationEval

# =============================================================================
# CONFIG  — change these to point at your tables
# =============================================================================
SOURCE_TABLE = "jp_customers_source"
TARGET_TABLE = "jp_customers_target"
KEY_COLUMN   = "customer_id"
COLUMNS      = ["name_jp", "product_jp", "city_jp"]
SCHEMA       = None   # None → uses DQ_DB_SCHEMA env var (default: "public")
# =============================================================================

# ── Connect and read ──────────────────────────────────────────────────────────
cfg    = DBConfig()
schema = SCHEMA or cfg.schema
engine = get_engine(cfg)

print(f"Reading {schema}.{SOURCE_TABLE} …")
source = read_table(engine, schema, SOURCE_TABLE)

print(f"Reading {schema}.{TARGET_TABLE} …")
target = read_table(engine, schema, TARGET_TABLE)

print(f"Source rows: {len(source)}  |  Target rows: {len(target)}\n")

# ── Run validation ────────────────────────────────────────────────────────────
result_json, failed_df = UnicodeValidationEval(
    DqEvalDataFrame(source),
    config={
        "key_column":         KEY_COLUMN,
        "columns":            COLUMNS,
        "target_df":          target,
        "normalization_form": "NFKC",
        "batch_size":         1000,
    },
).run(evaluation="advanced")

summary = json.loads(result_json)

# ── Build per-row status table ────────────────────────────────────────────────
failed_ids = set(failed_df[KEY_COLUMN].tolist()) if not failed_df.empty else set()

rows = []
for _, row in source.iterrows():
    kid = row[KEY_COLUMN]
    if kid in failed_ids:
        val = str(row[COLUMNS[0]] or "")
        if "\ufffd" in val:
            reason = "Replacement char (U+FFFD)"
        elif any( "\u00c2" <= c <= "\u00ef" for c in val) and any(
            "\u0080" <= c <= "\u00bf" for c in val
        ):
            reason = "Mojibake detected"
        else:
            reason = "Value mismatch"
        status = "FAIL"
    else:
        reason = "—"
        status = "PASS"

    tgt_row = target.loc[target[KEY_COLUMN] == kid, COLUMNS[0]]
    rows.append({
        KEY_COLUMN:                    kid,
        f"{COLUMNS[0]} (source)":      row[COLUMNS[0]],
        f"{COLUMNS[0]} (target)":      tgt_row.values[0] if len(tgt_row) else "NOT FOUND",
        "status":                      status,
        "reason":                      reason,
    })

status_df = pd.DataFrame(rows)

# ── Print results ─────────────────────────────────────────────────────────────
print("=" * 80)
print(f"ROW-BY-ROW RESULTS   source={SOURCE_TABLE}   target={TARGET_TABLE}")
print("=" * 80)
print(status_df.to_string(index=False))

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
summary_table = pd.DataFrame([
    {"metric": "Total rows in source",       "value": summary["dqeval_total_count"]},
    {"metric": "Rows matched (inner join)",  "value": summary["dqeval_matched_count"]},
    {"metric": "Passed",                     "value": summary["dqeval_passed_count"]},
    {"metric": "Failed",                     "value": summary["dqeval_failed_count"]},
    {"metric": "Mojibake detected",          "value": summary["dqeval_mojibake_count"]},
    {"metric": "Replacement chars (U+FFFD)", "value": summary["dqeval_replacement_char_count"]},
    {"metric": "Overall status",             "value": summary["status"]},
])
print(summary_table.to_string(index=False))
print()
