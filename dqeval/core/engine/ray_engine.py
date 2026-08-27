import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
import pandas as pd
import ray
from ray.data import Dataset as RayDataset

from dqeval.core.engine.base_engine import BaseEngine
from dqeval.utils.time_utils import parse_duration_to_timedelta

class RayEngine(BaseEngine):
    def __init__(self, df, run_id=None):
        super().__init__(df, run_id)
        self.columns = list(df.schema().names) if hasattr(df, "schema") else []

    def run_dup_eval(
        self,
        columns: List[str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        grouped = self.df.groupby(columns).count()
        dups = grouped.filter(lambda row: row["count()"] > 1)
        dup_keys = dups.take_all()
        dup_key_set = {tuple(row[col] for col in columns) for row in dup_keys}

        duplicate_rows = self.df.filter(lambda row: tuple(row[col] for col in columns) in dup_key_set)
        total = self.df.count()
        failed = duplicate_rows.count()

        result = self._build_result("duplicate_eval",total, failed)
        if evaluation == "advanced":
            return json.dumps(result, indent=2), duplicate_rows
        return json.dumps(result, indent=2)

    def run_empty_eval(
        self,
        columns: List[str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        empty_rows = self.df.filter(
            lambda row: any(row[col] is None or (isinstance(row[col], str) and row[col].strip() == '') for col in columns)
        )
        total = self.df.count()
        failed = empty_rows.count()
        result = self._build_result("empty_eval",total, failed)
        if evaluation == "advanced":
            return json.dumps(result, indent=2), empty_rows
        return json.dumps(result, indent=2)

    def run_unique_eval(
        self,
        columns: List[str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        # Group by the columns and count occurrences
        counts = self.df.groupby(columns).count()
        duplicates = counts.filter(lambda row: row["count()"] > 1)
        dup_rows = duplicates.take_all()
        if not dup_rows:
            dup_keys = set()
        else:
            # Each row is a dict; get the tuple of values for the columns
            dup_keys = set(tuple(row[col] for col in columns) for row in dup_rows)

        # Filter rows in the original dataset that match any duplicate key
        failed_df = self.df.filter(lambda row: tuple(row[col] for col in columns) in dup_keys if dup_keys else False)
        total = self.df.count()
        failed = failed_df.count()
        result = self._build_result("unique_eval",total, failed)
        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)

    def run_dtype_eval(
        self,
        column_types: Dict[str, str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        valid_types = {"int", "float", "bool", "str"}
        
        for col, expected in column_types.items():
            if expected not in valid_types:
                raise ValueError(f"Unsupported expected type '{expected}' for column '{col}'")
        
        def eval_row(row):
            for col, expected in column_types.items():
                val = row.get(col)
                if val is None:
                    continue
                try:
                    if expected == "int":
                        int(val)
                    elif expected == "float":
                        float(val)
                    elif expected == "bool":
                        if val not in [True, False]:
                            return True
                    elif expected == "str":
                        if not isinstance(val, str):
                            return True
                except:
                    return True
            return False

        failed_df = self.df.filter(eval_row)
        total = self.df.count()
        failed = failed_df.count()
        result = self._build_result("dtype_eval",total, failed)
        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)

    def run_range_eval(
        self,
        column: str,
        min_val: Any,
        max_val: Any,
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        failed_df = self.df.filter(lambda row: not (min_val <= row[column] <= max_val))
        total = self.df.count()
        failed = failed_df.count()
        result = self._build_result("range_eval",total, failed)
        result["column"] = column
        result["range"] = {"min": min_val, "max": max_val}
        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)

    def run_stringformat_eval(
        self,
        column: str,
        pattern: str,
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        import re
        regex = re.compile(pattern)
        failed_df = self.df.filter(lambda row: not regex.fullmatch(str(row[column]) or ''))
        total = self.df.count()
        failed = failed_df.count()
        result = self._build_result("stringformat_eval",total, failed)
        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)

    def run_categoricalvalues_eval(
        self,
        column: str,
        allowed_values: List[Any],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, RayDataset]]:
        allowed_set = set(allowed_values)
        failed_df = self.df.filter(lambda row: row[column] not in allowed_set)
        total = self.df.count()
        failed = failed_df.count()
        result = self._build_result("categoricalvalues_eval",total, failed)
        result["allowed_values"] = allowed_values
        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)

    def run_rowcount_eval(
        self,
        min_rows: Optional[int] = None,
        max_rows: Optional[int] = None
    ) -> str:
        total = self.df.count()
        status = "Success"
        if (min_rows is not None and total < min_rows) or (max_rows is not None and total > max_rows):
            status = "Failed"
        passed = True if status =="Success" else False
        result = {
            "status": status,
            "dqeval_type": "rowcount_eval",
            "dqeval_passed": passed,
            "dqeval_total_count": total,
            "min_required": min_rows,
            "max_allowed": max_rows,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        return json.dumps(result, indent=2)

    def run_custom_eval(
        self,
        column: Optional[str],
        expression: Callable[[Any], bool],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, "RayDataset"]]:
        """
        Run a custom eval using a user-provided function (Ray version).

        Args:
            column: Column name to apply the function to. If None, applies to each row as a dict.
            expression: Callable that returns True if value/row passes, False otherwise.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, RayDataset).

        Returns:
            JSON string (and Ray Dataset of failed rows if advanced).
        """
        import json
        from datetime import datetime, timezone

        if column:
            failed_df = self.df.filter(lambda row: not expression(row[column]))
            eval = "custom_eval_column"
        else:
            failed_df = self.df.filter(lambda row: not expression(row))
            eval = "custom_eval_row"

        total = self.df.count()
        failed = failed_df.count()

        result = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": eval,
            "column": column,
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_df
        return json.dumps(result, indent=2)


    def run_datafreshness_eval(
        self,
        column: str,
        freshness_threshold: str
    ) -> str:
        import ray
        import json
        import pandas as pd
        from datetime import datetime, timezone

        if column not in self.df.schema().names:
            raise ValueError(f"Column '{column}' not found in dataset.")

        timedelta = parse_duration_to_timedelta(freshness_threshold)

        if timedelta.total_seconds() < 0:
            raise ValueError("Freshness threshold cannot be negative (i.e., in the future).")

        def extract_valid_timestamp(row):
            val = row[column]
            if val is None:
                return None
            try:
                ts = pd.to_datetime(val, errors="coerce")
                if pd.isnull(ts):
                    return None
                return ts
            except Exception:
                return None

        ts_dataset = self.df.map(lambda row: {column: extract_valid_timestamp(row)})
        ts_dataset = ts_dataset.filter(lambda r: r[column] is not None)
        latest_ts = ts_dataset.max(column)

        if latest_ts is None:
            raise TypeError(f"Column '{column}' contains no valid datetime values.")

        # Normalize to UTC if naive
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)

        cutoff_ts = datetime.now(timezone.utc) - timedelta
        passed = latest_ts > cutoff_ts

        result = {
            "status": "Success" if passed else "Failed",
            "dqeval_type": "datafreshness_eval",
            "column": column,
            "latest_timestamp": str(latest_ts),
            "cutoff_timestamp": str(cutoff_ts),
            "dqeval_passed": bool(passed),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }

        return json.dumps(result, indent=2)


    def _build_result(self,eval: str, total: int, failed: int) -> Dict[str, Any]:
        return {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": eval,
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
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
        import pandas as pd
        from scipy.stats import ks_2samp
        from datetime import datetime, timezone
        import json

        df_pd = self.df.to_pandas()

        if column not in df_pd.columns:
            raise ValueError(f"Column '{column}' not found.")

        if mode == "feature_drift":
            if reference_stats is None:
                raise ValueError("reference_stats must be provided for feature_drift mode.")

            current_mean = df_pd[column].mean()
            current_std = df_pd[column].std()

            drift_mean = abs(current_mean - reference_stats["mean"])
            drift_std = abs(current_std - reference_stats["std"])

            passed = drift_mean <= tolerance and drift_std <= tolerance

            result_dict = {
                "status": "Success" if passed else "Failed",
                "dqeval_type": "statisticaldistribution_eval",
                "mode": "feature_drift",
                "column": column,
                "dqeval_drift_mean": float(drift_mean),
                "dqeval_drift_std": float(drift_std),
                "dqeval_passed": bool(passed),
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id,
            }
            return json.dumps(result_dict, indent=2)

        elif mode == "label_balance":
            counts = df_pd[column].value_counts(normalize=True).to_dict()
            max_class_ratio = max(counts.values())
            imbalance_threshold = 0.9
            passed = max_class_ratio <= imbalance_threshold

            result_dict = {
                "status": "Success" if passed else "Failed",
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
            raise ValueError("Unsupported statistical eval mode.")

    def run_schemavalidation_eval(
        self,
        expected_schema: Dict[str, Any]
    ) -> str:
        import json
        from datetime import datetime, timezone

        actual_schema = {
            name: str(typ) for name, typ in zip(self.df.schema().names, self.df.schema().types)
        }

        missing_columns = [col for col in expected_schema if col not in actual_schema]
        mismatched_types = {}

        for col, expected_dtype in expected_schema.items():
            if col in actual_schema:
                if str(expected_dtype).lower() != actual_schema[col].lower():
                    mismatched_types[col] = {
                        "expected": str(expected_dtype),
                        "actual": actual_schema[col]
                    }

        status = "Success" if not missing_columns and not mismatched_types else "Failed"

        result_dict = {
            "status": status,
            "dqeval_type": "schemavalidation_eval",
            "missing_columns": missing_columns,
            "type_mismatches": mismatched_types,
            "dqeval_total_count": self.df.count(),
            "dqeval_failed_count": len(missing_columns) + len(mismatched_types),
            "dqeval_passed_count": len(expected_schema) - len(missing_columns) - len(mismatched_types),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
        }

        return json.dumps(result_dict, indent=2)


    def run_referential_integrity_eval(
        self,
        column: str,
        reference_df: "ray.data.Dataset",
        reference_column: str,
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, "ray.data.Dataset"]]:
        """
        eval referential integrity between a column and a reference dataset using Ray only.

        Args:
            column: Column in this dataset.
            reference_df: Reference Ray Dataset.
            reference_column: Column in the reference dataset.
            evaluation: "basic" or "advanced".

        Returns:
            JSON result string, and failed Ray dataset if evaluation is "advanced".
        """
        import json
        from datetime import datetime, timezone

        reference_rows = reference_df.select_columns([reference_column]).take_all()
        reference_values = set(row[reference_column] for row in reference_rows)

        failed_ds = self.df.filter(lambda row: row[column] not in reference_values)

        total = self.df.count()
        failed = failed_ds.count()

        result = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "referentialintegrity_eval",
            "column": column,
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }

        if evaluation == "advanced":
            return json.dumps(result, indent=2), failed_ds

        return json.dumps(result, indent=2)



