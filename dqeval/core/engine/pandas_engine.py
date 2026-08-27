import hashlib
import logging
import re
import unicodedata
import numpy as np
import pandas
import pandas as pd
import json
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from dqeval.core.engine.base_engine import BaseEngine
from dqeval.utils.time_utils import parse_duration_to_timedelta
from datetime import datetime, timezone
from pandas.api.types import (
    is_integer, is_float, is_string_dtype,
    is_bool, is_datetime64_any_dtype,
    is_timedelta64_dtype, is_categorical_dtype
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mojibake detection
# ---------------------------------------------------------------------------
# Mojibake arises when multi-byte UTF-8 sequences are decoded as a single-byte
# encoding (typically Latin-1 / Windows-1252).  In the resulting Unicode string
# the tell-tale pattern is a high-Latin character (U+00C2–U+00EF) immediately
# followed by a continuation-like character (U+0080–U+00BF).  This covers the
# most common 2-byte and 3-byte UTF-8 sequences misread as Latin-1.
#
# Examples of mojibake this catches:
#   "Ã©"  (U+00C3 U+00A9)  →  should be "é"
#   "Ã‚"  (U+00C3 U+0082)  →  should be "Â" (less common but real)
#   "â€œ" (U+00E2 U+0080 U+009C)  →  should be """ (LEFT DOUBLE QUOTATION)
_MOJIBAKE_RE = re.compile(
    r"[\u00C2-\u00EF][\u0080-\u00BF]"       # 2-byte UTF-8 sequence as Latin-1
    r"|[\u00E0-\u00EF][\u0080-\u00BF]{2}"   # 3-byte UTF-8 sequence as Latin-1
)
# U+FFFD is the Unicode replacement character emitted when a decoder encounters
# an invalid byte sequence that it cannot represent.
_REPLACEMENT_CHAR = "\ufffd"

class PandasEngine(BaseEngine):

    def run_dup_eval(
        self, 
        columns: List[str], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval for duplicate rows based on specified columns.

        Args:
            columns: List of column names to eval for duplicates.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """

        duplicates = self.df[self.df.duplicated(subset=columns, keep=False)]
        total = self.df.shape[0]
        failed = duplicates.shape[0]
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "duplicate_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), duplicates
        return json.dumps(result_dict, indent=2)

    def run_empty_eval(
        self, 
        columns: List[str], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval for empty (null or blank) values in specified columns.

        Args:
            columns: List of column names to eval for empties.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        empty_rows = self.df[self.df[columns].isnull().any(axis=1) | (self.df[columns] == '').any(axis=1)]
        total = self.df.shape[0]
        failed = empty_rows.shape[0]
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "empty_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), empty_rows
        return json.dumps(result_dict, indent=2)

    def run_unique_eval(
        self,
        columns: List[str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval for uniqueness in specified columns.

        Args:
            columns: List of column names to eval for uniqueness.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        duplicates = self.df[self.df.duplicated(subset=columns, keep=False)]
        total = self.df.shape[0]
        failed = duplicates.shape[0]
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "unique_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), duplicates
        return json.dumps(result_dict, indent=2)
    
    def run_dtype_eval(
        self,
        column_types: Dict[str, str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        Evaluate whether columns in the DataFrame match expected dtypes.
        
        Args:
            column_types: Dict mapping column names to expected dtypes.
            evaluation: "basic" returns JSON summary;
                        "advanced" returns (JSON summary, failed DataFrame).

        Returns:
            JSON string (and DataFrame if evaluation == "advanced").
        """
        import numpy as np
        import pandas as pd
        from datetime import datetime, timezone
        import json

        df = self.df.copy()
        failed_mask = pd.Series([False] * len(df), index=df.index)

        # Normalize dtype names (e.g., 'Int64' → 'int64', 'STRING' → 'string')
        def normalize_dtype(dtype_str):
            return str(dtype_str).lower().replace(" ", "")

        # Supported dtype families
        numeric_types = {"int", "int8", "int16", "int32", "int64",
                        "float", "float16", "float32", "float64", "complex", "complex64", "complex128"}
        datetime_types = {"datetime", "datetime64", "datetime64[ns]"}
        timedelta_types = {"timedelta", "timedelta64", "timedelta64[ns]"}
        bool_types = {"bool", "boolean"}
        string_types = {"str", "string", "object"}
        categorical_types = {"category"}
        
        for col, expected_dtype in column_types.items():
            if col not in df.columns:
                raise KeyError(f"Column '{col}' not found in DataFrame.")
            
            expected_dtype = normalize_dtype(expected_dtype)

            try:
                # Validation per dtype group
                if any(t in expected_dtype for t in numeric_types):
                    converted = pd.to_numeric(df[col], errors="coerce")
                    fail_col = converted.isna() & df[col].notna()

                elif expected_dtype in datetime_types:
                    converted = pd.to_datetime(df[col], errors="coerce")
                    fail_col = converted.isna() & df[col].notna()

                elif expected_dtype in timedelta_types:
                    converted = pd.to_timedelta(df[col], errors="coerce")
                    fail_col = converted.isna() & df[col].notna()

                elif expected_dtype in bool_types:
                    # Handle native and pandas nullable boolean types
                    valid_vals = [True, False, np.nan, pd.NA]
                    fail_col = ~df[col].isin(valid_vals)

                elif expected_dtype in string_types:
                    fail_col = ~df[col].apply(lambda x: isinstance(x, str) or pd.isna(x))

                elif expected_dtype in categorical_types:
                    fail_col = ~pd.api.types.is_categorical_dtype(df[col])

                else:
                    # Fallback to pandas dtype inference
                    try:
                        converted = df[col].astype(expected_dtype)
                        fail_col = pd.Series(False, index=df.index)
                    except Exception:
                        fail_col = pd.Series(True, index=df.index)

            except Exception as e:
                # Any unhandled exception → mark all rows as failed for that column
                fail_col = pd.Series(True, index=df.index)

            failed_mask |= fail_col

        failed_df = df[failed_mask]
        total = len(df)
        failed = len(failed_df)

        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "dtype_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": getattr(self, "run_id", None)
        }

        result_json = json.dumps(result_dict, indent=2)
        if evaluation == "advanced":
            return result_json, failed_df
        return result_json

    
    def run_stringformat_eval(
        self, 
        column: str, 
        pattern: str, 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval if string values in a column match a regex pattern.

        Args:
            column: Column name to eval.
            pattern: Regex pattern to match.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        mask = ~self.df[column].astype(str).str.match(pattern)
        failed_rows = self.df[mask]
        total = self.df.shape[0]
        failed = failed_rows.shape[0]
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "stringformat_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), failed_rows
        return json.dumps(result_dict, indent=2)
    
    def run_schemavalidation_eval(
        self, 
        expected_schema: Dict[str, Any]
    ) -> str:
        """
        Validate DataFrame schema against expected schema.

        Args:
            expected_schema: Dict mapping column names to expected dtypes.

        Returns:
            JSON string with schema validation results.
        """
        df = self.df
        missing_columns = [col for col in expected_schema if col not in df.columns]
        mismatched_types = {}

        for col, expected_dtype in expected_schema.items():
            if col not in df.columns:
                continue
            actual_dtype = df[col].dtype

            # Normalize types to string
            if isinstance(expected_dtype, type):
                expected_dtype = np.dtype(expected_dtype)
            else:
                expected_dtype = np.dtype(expected_dtype)

            if actual_dtype != expected_dtype:
                mismatched_types[col] = {
                    "expected": str(expected_dtype),
                    "actual": str(actual_dtype)
                }

        status = "Success" if not missing_columns and not mismatched_types else "Failed"

        result_dict = {
            "status": status,
            "dqeval_type": "schemavalidation_eval",
            "missing_columns": missing_columns,
            "type_mismatches": mismatched_types,
            "dqeval_total_count": df.shape[0],
            "dqeval_failed_count": len(missing_columns) + len(mismatched_types),
            "dqeval_passed_count": len(expected_schema) - len(missing_columns) - len(mismatched_types),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        return json.dumps(result_dict, indent=2)
    
    def run_range_eval(
        self, 
        column: str, 
        min_val: Any, 
        max_val: Any, 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval if values in a column fall within a specified range.

        Args:
            column: Column name to eval.
            min_val: Minimum allowed value.
            max_val: Maximum allowed value.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")

        # Identify rows outside range
        mask = ~df[column].between(min_val, max_val)
        failed_count = mask.sum()
        total_count = len(df)
        passed_count = total_count - failed_count

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "range_eval",
            "column": column,
            "range": {"min": min_val, "max": max_val},
            "dqeval_total_count": total_count,
            "dqeval_failed_count": int(failed_count),
            "dqeval_passed_count": int(passed_count),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), df[mask]
        return json.dumps(result_dict, indent=2)
    
    def run_categoricalvalues_eval(
        self, 
        column: str, 
        allowed_values: List[Any], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval if values in a column are within allowed categorical values.

        Args:
            column: Column name to eval.
            allowed_values: List of allowed values.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")

        mask = ~df[column].isin(allowed_values)
        failed_count = mask.sum()
        total_count = len(df)
        passed_count = total_count - failed_count

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "categoricalvalues_eval",
            "column": column,
            "allowed_values": allowed_values,
            "dqeval_total_count": total_count,
            "dqeval_failed_count": int(failed_count),
            "dqeval_passed_count": int(passed_count),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), df[mask]
        return json.dumps(result_dict, indent=2)
    
    def run_statisticaldistribution_eval(
        self, 
        column: str, 
        mode: str, 
        reference_stats: Optional[Dict[str, float]] = None, 
        tolerance: float = 0.05
    ) -> str:
        """
        eval statistical distribution of a column for drift or label balance.

        Args:
            column: Column name to eval.
            mode: "feature_drift" or "label_balance".
            reference_stats: Reference statistics for drift eval.
            tolerance: Allowed tolerance for drift.

        Returns:
            JSON string with statistical eval results.
        """
        import numpy as np
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found.")

        if mode == "feature_drift":
            current_mean = df[column].mean()
            current_std = df[column].std()

            drift_mean = abs(current_mean - reference_stats["mean"])
            drift_std = abs(current_std - reference_stats["std"])

            passed = drift_mean <= tolerance and drift_std <= tolerance

            result_dict = {
                "status": "Success" if bool(passed) else "Failed",
                "dqeval_type": "statisticaldistribution_eval",
                "mode": "feature_drift",
                "column": column,
                "dqeval_drift_mean": float(drift_mean),
                "dqeval_drift_std": float(drift_std),
                "dqeval_passed": bool(passed),
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id
            }
            return json.dumps(result_dict, indent=2)

        elif mode == "label_balance":
            counts = df[column].value_counts(normalize=True).to_dict()
            max_class_ratio = max(counts.values())
            imbalance_threshold = 0.9  # configurable if needed
            passed = max_class_ratio <= imbalance_threshold

            result_dict = {
                "status": "Success" if bool(passed) else "Failed",
                "dqeval_type": "statisticaldistribution_eval",
                "mode": "label_balance",
                "column": column,
                "dqeval_distribution": counts,
                "dqeval_passed": bool(passed),
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id
            }
            return json.dumps(result_dict, indent=2)

        else:
            raise ValueError("Unsupported statistical eval mode")
        
    def run_datafreshness_eval(
        self, 
        column: str, 
        freshness_threshold: str
    ) -> str:
        """
        eval if the latest timestamp in a column is within the freshness threshold.

        Args:
            column: Column name to eval (must be datetime type).
            freshness_threshold: Freshness threshold as a duration string (e.g., '1d', '12h', '15m').

        Returns:
            JSON string with freshness eval results.
        """
        import pandas as pd
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found.")

        if not pd.api.types.is_datetime64_any_dtype(df[column]):
            raise TypeError(f"Column '{column}' must be of datetime type.")

        latest_timestamp = df[column].max()
        freshness_cutoff = pd.Timestamp.now() - parse_duration_to_timedelta(freshness_threshold)
        passed = latest_timestamp > freshness_cutoff

        result_dict = {
            "status": "Success" if passed else "Failed",
            "dqeval_type": "datafreshness_eval",
            "column": column,
            "latest_timestamp": str(latest_timestamp),
            "cutoff_timestamp": str(freshness_cutoff),
            "dqeval_passed": passed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        return json.dumps(result_dict, indent=2)
    
    def run_referential_integrity_eval(
        self, 
        column: str, 
        reference_df: pd.DataFrame, 
        reference_column: str, 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        eval referential integrity between a column and a reference DataFrame column.

        Args:
            column: Column in the main DataFrame.
            reference_df: Reference DataFrame.
            reference_column: Column in the reference DataFrame.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        invalid_rows = self.df[~self.df[column].isin(reference_df[reference_column])]
        total = self.df.shape[0]
        failed = invalid_rows.shape[0]
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "referentialintegrity_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), invalid_rows
        return json.dumps(result_dict, indent=2)
    
    def run_rowcount_eval(
        self, 
        min_rows: Optional[int] = None, 
        max_rows: Optional[int] = None
    ) -> str:
        """
        eval if the number of rows is within the specified bounds.

        Args:
            min_rows: Minimum allowed number of rows.
            max_rows: Maximum allowed number of rows.

        Returns:
            JSON string with row count eval results.
        """
        total = self.df.shape[0]

        status = "Success"
        if (min_rows is not None and total < min_rows) or (max_rows is not None and total > max_rows):
            status = "Failed"
        passed = True if status =="Success" else False

        result_dict = {
            "status": status,
            "dqeval_type": "rowcount_eval",
            "dqeval_passed": passed,
            "dqeval_total_count": total,
            "min_required": min_rows,
            "max_allowed": max_rows,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        return json.dumps(result_dict, indent=2)
    
    def run_custom_eval(
        self, 
        column: Optional[str], 
        expression: Callable[[Any], bool], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        Run a custom eval using a user-provided function.

        Args:
            column: Column name to apply the function to. If None, applies to each row as a dict.
            expression: Callable that returns True if value/row passes, False otherwise.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        total = self.df.shape[0]

        if callable(expression):
            func = expression
        else:
            raise ValueError("`expression` must be a callable or a string representing a lambda.")
        
        if column:
            mask = ~self.df[column].apply(func)
            eval = "custom_eval_column"
        else:
            mask = ~self.df.apply(lambda row: func(row.to_dict()), axis=1)
            eval = "custom_eval_row"

        failed_df = self.df[mask]
        failed_count = failed_df.shape[0]

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": eval,
            "column": column,
            "dqeval_total_count": total,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": total - failed_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }

        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), failed_df
        return json.dumps(result_dict, indent=2)

    # ------------------------------------------------------------------
    # Unicode Validation
    # ------------------------------------------------------------------

    def run_unicode_validation_eval(
        self,
        key_column: str,
        columns: List[str],
        target_df: pd.DataFrame,
        target_columns: List[str],
        normalization_form: str = "NFC",
        batch_size: int = 1000,
        evaluation: str = "basic",
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        Compare Unicode text columns between source (self.df) and target_df.

        Algorithm (per batch of merged rows)
        -------------------------------------
        For every row that is present in *both* tables (inner-joined on
        ``key_column``) and for every configured column pair:

        1.  Convert to ``str``; treat ``None`` / ``NaN`` as empty string so
            the comparison is well-defined even for nullable columns.
        2.  Normalise with ``unicodedata.normalize(normalization_form, value)``
            so that canonically-equivalent code-point sequences (e.g. precomposed
            vs. decomposed accented characters) compare as equal.  This mirrors
            PostgreSQL's ``normalize(text, NFC)`` and prevents false negatives
            caused purely by normalisation-form differences in the ETL pipeline.
        3.  Hash the UTF-8-encoded normalised string with SHA-256.  Hashing
            avoids exposing raw PII in the result payload and is faster than
            string comparison for long text values.
        4.  Detect the Unicode replacement character U+FFFD in the *source*
            value — a definitive sign of a lossless encoding failure.
        5.  Detect mojibake in the *source* value — multi-byte UTF-8 sequences
            accidentally decoded as Latin-1 (see module-level ``_MOJIBAKE_RE``).
        6.  Mark the row as *failed* if the source hash != target hash, OR if
            a replacement character or mojibake is present in the source value.

        Mojibake is checked on the *source* value separately (step 5) because
        if *both* sides carry the same mojibake the hashes will match, hiding
        the corruption.  Detecting it at source surfaces the problem regardless.

        Parameters
        ----------
        key_column : str
            Column used to align rows between source and target (inner join).
        columns : list[str]
            Column names in the source DataFrame.
        target_df : pd.DataFrame
            The target DataFrame to compare against.
        target_columns : list[str]
            Column names in ``target_df`` corresponding to ``columns``.
        normalization_form : str
            ``unicodedata.normalize`` form.  Default ``"NFC"``.
        batch_size : int
            Rows per processing batch.  Default ``1000``.
        evaluation : str
            ``"basic"`` → JSON string.
            ``"advanced"`` → ``(json_string, failed_rows_dataframe)``.

        Returns
        -------
        str | tuple[str, pd.DataFrame]
        """
        source = self.df
        total_source_rows = len(source)

        # ── Inner-join source and target on the key column ───────────────────
        # Rename target columns to avoid pandas suffix conflicts while
        # preserving the original column names for the result DataFrame.
        target_rename = {col: f"__tgt_{col}" for col in target_columns}
        target_rename[key_column] = key_column  # keep the join key as-is

        target_subset = target_df[[key_column] + target_columns].rename(
            columns={col: f"__tgt_{col}" for col in target_columns}
        )

        merged = source.merge(target_subset, on=key_column, how="inner")
        matched_count = len(merged)

        logger.info(
            "Unicode validation | source_rows=%d | matched_rows=%d | "
            "batch_size=%d | normalization_form=%s",
            total_source_rows,
            matched_count,
            batch_size,
            normalization_form,
        )

        # ── Per-row evaluation accumulators ──────────────────────────────────
        failed_mask = pd.Series(False, index=merged.index)
        mojibake_mask = pd.Series(False, index=merged.index)
        replacement_char_mask = pd.Series(False, index=merged.index)

        # ── Batch loop ───────────────────────────────────────────────────────
        num_batches = max(1, (matched_count + batch_size - 1) // batch_size)

        for batch_idx in range(num_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, matched_count)
            batch = merged.iloc[start:end]

            logger.debug(
                "Processing batch %d/%d (rows %d–%d)",
                batch_idx + 1,
                num_batches,
                start,
                end - 1,
            )

            for src_col, tgt_col in zip(columns, target_columns):
                tgt_merged_col = f"__tgt_{tgt_col}"

                # -- Normalise & hash both sides for the current column -------
                def _normalise_hash(raw) -> str:
                    """Return SHA-256 hex digest of the NFC-normalised string."""
                    text = "" if (raw is None or (isinstance(raw, float) and pd.isna(raw))) else str(raw)
                    normalised = unicodedata.normalize(normalization_form, text)
                    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

                src_hashes = batch[src_col].map(_normalise_hash)
                tgt_hashes = batch[tgt_merged_col].map(_normalise_hash)

                # Hash mismatch → row fails
                col_hash_fail = src_hashes != tgt_hashes
                failed_mask.loc[batch.index] |= col_hash_fail

                # -- Replacement character detection --------------------------
                def _has_replacement_char(raw) -> bool:
                    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                        return False
                    return _REPLACEMENT_CHAR in str(raw)

                col_repl = batch[src_col].map(_has_replacement_char)
                replacement_char_mask.loc[batch.index] |= col_repl
                failed_mask.loc[batch.index] |= col_repl

                # -- Mojibake detection ---------------------------------------
                def _has_mojibake(raw) -> bool:
                    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                        return False
                    return bool(_MOJIBAKE_RE.search(str(raw)))

                col_mojibake = batch[src_col].map(_has_mojibake)
                mojibake_mask.loc[batch.index] |= col_mojibake
                failed_mask.loc[batch.index] |= col_mojibake

        # ── Aggregate results ─────────────────────────────────────────────────
        failed_rows = merged[failed_mask].copy()

        # Expose only source columns + key in the failed rows output; strip
        # the internal __tgt_* helper columns so consumers see clean data.
        source_cols_in_merged = [key_column] + [
            c for c in merged.columns
            if c in source.columns and c != key_column
        ]
        failed_rows_clean = failed_rows[source_cols_in_merged]

        failed_count = int(failed_mask.sum())
        mojibake_count = int(mojibake_mask.sum())
        replacement_char_count = int(replacement_char_mask.sum())
        passed_count = matched_count - failed_count

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "unicode_validation_eval",
            "key_column": key_column,
            "columns_checked": columns,
            "normalization_form": normalization_form,
            "dqeval_total_count": total_source_rows,
            "dqeval_matched_count": matched_count,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": passed_count,
            "dqeval_mojibake_count": mojibake_count,
            "dqeval_replacement_char_count": replacement_char_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

        logger.info(
            "Unicode validation complete | status=%s | matched=%d | "
            "failed=%d | mojibake=%d | replacement_chars=%d",
            result_dict["status"],
            matched_count,
            failed_count,
            mojibake_count,
            replacement_char_count,
        )

        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), failed_rows_clean
        return json.dumps(result_dict, indent=2)

    # ------------------------------------------------------------------
    # Date Range Validation
    # ------------------------------------------------------------------

    def run_daterange_eval(
        self,
        column: str,
        min_date: str,
        max_date: str,
        date_format: str = "%Y-%m-%d",
        evaluation: str = "basic",
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        Verify that date/datetime values in a column fall within [min_date, max_date].

        Args:
            column: Column name containing date values.
            min_date: Lower bound date string.
            max_date: Upper bound date string.
            date_format: strftime format used to parse min_date/max_date.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).
        """
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")

        parsed_min = pd.to_datetime(min_date, format=date_format)
        parsed_max = pd.to_datetime(max_date, format=date_format)

        col_dates = pd.to_datetime(df[column], errors="coerce")
        # Rows that are NaT after coercion or outside the range
        mask = col_dates.isna() | (col_dates < parsed_min) | (col_dates > parsed_max)
        failed_count = int(mask.sum())
        total_count = len(df)

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "daterange_eval",
            "column": column,
            "date_range": {"min_date": min_date, "max_date": max_date},
            "date_format": date_format,
            "dqeval_total_count": total_count,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": total_count - failed_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), df[mask]
        return json.dumps(result_dict, indent=2)

    # ------------------------------------------------------------------
    # Mojibake Detection
    # ------------------------------------------------------------------

    def run_mojibake_eval(
        self,
        column: str,
        evaluation: str = "basic",
    ) -> Union[str, Tuple[str, pd.DataFrame]]:
        """
        Detect mojibake (garbled text from encoding mismatches) in a column.

        Args:
            column: Column name containing string values.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).
        """
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")

        def _has_mojibake(val) -> bool:
            if not isinstance(val, str):
                return False
            if _REPLACEMENT_CHAR in val:
                return True
            if _MOJIBAKE_RE.search(val):
                return True
            return False

        mask = df[column].apply(_has_mojibake)
        failed_count = int(mask.sum())
        total_count = len(df)

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "mojibake_eval",
            "column": column,
            "dqeval_total_count": total_count,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": total_count - failed_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), df[mask]
        return json.dumps(result_dict, indent=2)
