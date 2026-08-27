from functools import reduce
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, udf, struct
from pyspark.sql.types import *
from dqeval.core.engine.base_engine import BaseEngine
from dqeval.utils.time_utils import parse_duration_to_timedelta
import json
from datetime import datetime, timezone

class SparkEngine(BaseEngine):

    def run_dup_eval(self, columns:List[str], evaluation: str="basic")-> Union[str, Tuple[str, DataFrame]]:
        """
        eval for duplicate rows based on specified columns.

        Args:
            columns: List of column names to eval for duplicates.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        grouped = self.df.groupBy(columns).count().filter("count > 1")
        duplicates = self.df.join(grouped, on=columns, how='inner')
        total = self.df.count()
        failed = duplicates.count()
        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "duplicate_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": total - failed,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),  # ISO UTC format
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), duplicates
        return json.dumps(result_dict, indent=2)

    def run_empty_eval(self, columns: List[str], evaluation:str="basic")-> Union[str, Tuple[str, DataFrame]]:
        """
        eval for empty (null or blank) values in specified columns.

        Args:
            columns: List of column names to eval for empties.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        conditions = [col(c).isNull() | (col(c) == '') for c in columns]
        combined = reduce(lambda a, b: a | b, conditions)
        empty_rows = self.df.filter(combined)
        total = self.df.count()
        failed = empty_rows.count()
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
    
    def run_unique_eval(self, column:str, evaluation:str="basic")-> Union[str, Tuple[str, DataFrame]]:
        """
        eval for uniqueness in a specified column.

        Args:
            column: Column name to eval for uniqueness.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        grouped = self.df.groupBy(column).count().filter("count > 1")
        non_unique = self.df.join(grouped, on=column, how='inner')
        total = self.df.count()
        failed = non_unique.count()
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
            return json.dumps(result_dict, indent=2), non_unique
        return json.dumps(result_dict, indent=2)
    
    def run_dtype_eval(
        self,
        column_types: Dict[str, str],
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, DataFrame]]:
        """
        Evaluate if DataFrame columns match expected Spark data types.

        Args:
            column_types: Dict mapping column names to expected Spark dtypes (e.g., 'string', 'int', 'decimal(10,2)').
            evaluation: "basic" returns JSON summary;
                        "advanced" returns (JSON summary, failed DataFrame).

        Returns:
            JSON string (and DataFrame if evaluation == "advanced").
        """
        import json
        from datetime import datetime, timezone
        from pyspark.sql import functions as F
        from pyspark.sql.types import (
            ByteType, ShortType, IntegerType, LongType,
            FloatType, DoubleType, DecimalType,
            BooleanType, StringType, BinaryType,
            TimestampType, DateType,
            ArrayType, MapType, StructType
        )

        spark_type_map = {
            "byte": ByteType,
            "short": ShortType,
            "int": IntegerType,
            "integer": IntegerType,
            "bigint": LongType,
            "long": LongType,
            "float": FloatType,
            "double": DoubleType,
            "decimal": DecimalType,  # will parse precision/scale if given
            "bool": BooleanType,
            "boolean": BooleanType,
            "str": StringType,
            "string": StringType,
            "binary": BinaryType,
            "timestamp": TimestampType,
            "datetime": TimestampType,
            "date": DateType,
            "array": ArrayType,
            "map": MapType,
            "struct": StructType,
        }

        df = self.df
        failed_df = None

        def parse_decimal_type(type_str: str):
            """Parses decimal(precision, scale) if specified."""
            import re
            match = re.match(r"decimal\((\d+),\s*(\d+)\)", type_str)
            if match:
                precision, scale = map(int, match.groups())
                return DecimalType(precision, scale)
            return DecimalType(38, 18)  # default Spark max precision

        for col_name, expected_dtype in column_types.items():
            expected_dtype_lower = expected_dtype.lower().strip()

            # Handle special case for decimal types
            if expected_dtype_lower.startswith("decimal"):
                spark_type_instance = parse_decimal_type(expected_dtype_lower)
            else:
                spark_type_cls = spark_type_map.get(expected_dtype_lower)
                if not spark_type_cls:
                    # Unknown dtype → automatically fail
                    fail_col_df = df
                    if failed_df is None:
                        failed_df = fail_col_df
                    else:
                        failed_df = failed_df.unionByName(fail_col_df).dropDuplicates()
                    continue
                spark_type_instance = spark_type_cls()

            casted = df.withColumn(f"__cast_{col_name}", F.col(col_name).cast(spark_type_instance))
            fail_col_df = (
                casted.filter(F.col(col_name).isNotNull() & F.col(f"__cast_{col_name}").isNull())
                    .drop(f"__cast_{col_name}")
            )

            if failed_df is None:
                failed_df = fail_col_df
            else:
                failed_df = failed_df.unionByName(fail_col_df).dropDuplicates()

        total = df.count()
        failed = failed_df.count() if failed_df is not None else 0
        passed = total - failed

        result_dict = {
            "status": "Success" if failed == 0 else "Failed",
            "dqeval_type": "dtype_eval",
            "dqeval_total_count": total,
            "dqeval_failed_count": failed,
            "dqeval_passed_count": passed,
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
    ) -> Union[str, Tuple[str, DataFrame]]:
        """
        eval if string values in a column match a regex pattern.

        Args:
            column: Column name to eval.
            pattern: Regex pattern to match.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        import re
        regex_udf = (lambda value: not bool(re.match(pattern, str(value))) if value is not None else True)
        from pyspark.sql.functions import udf
        from pyspark.sql.types import BooleanType

        mismatch_udf = udf(regex_udf, BooleanType())
        mismatches = self.df.filter(mismatch_udf(col(column)))

        total = self.df.count()
        failed = mismatches.count()

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
            return json.dumps(result_dict, indent=2), mismatches
        return json.dumps(result_dict, indent=2)
    
    def run_schemavalidation_eval(
        self, 
        expected_schema: Dict[str, str]
    ) -> str:
        """
        Validate DataFrame schema against expected schema.

        Args:
            expected_schema: Dict mapping column names to expected Spark dtypes.

        Returns:
            JSON string with schema validation results.
        """
        df = self.df
        schema_fields = {f.name: f.dataType for f in df.schema.fields}

        missing_columns = [col for col in expected_schema if col not in schema_fields]
        mismatched_types = {}

        spark_type_mapping = {
            "int": IntegerType(),
            "float": FloatType(),
            "double": DoubleType(),
            "string": StringType(),
            "long": LongType(),
            "boolean": BooleanType(),
            "timestamp": TimestampType(),
            "date": DateType()
        }

        for col, expected_dtype in expected_schema.items():
            if col not in schema_fields:
                continue

            actual_type = schema_fields[col]
            expected_type = spark_type_mapping.get(expected_dtype.lower())

            if expected_type is None:
                mismatched_types[col] = {
                    "expected": f"(Unsupported expected type: {expected_dtype})",
                    "actual": actual_type.simpleString()
                }
                continue

            if not isinstance(actual_type, type(expected_type)):
                mismatched_types[col] = {
                    "expected": expected_type.simpleString(),
                    "actual": actual_type.simpleString()
                }

        status = "Success" if not missing_columns and not mismatched_types else "Failed"

        result_dict = {
            "status": status,
            "dqeval_type": "schemavalidation_eval",
            "missing_columns": missing_columns,
            "type_mismatches": mismatched_types,
            "dqeval_total_count": df.count(),
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
    ) -> Union[str, Tuple[str, DataFrame]]:
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

        invalid_df = df.filter((col(column) < min_val) | (col(column) > max_val))
        failed_count = invalid_df.count()
        total_count = df.count()
        passed_count = total_count - failed_count

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "range_eval",
            "column": column,
            "range": {"min": min_val, "max": max_val},
            "dqeval_total_count": total_count,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": passed_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), invalid_df
        return json.dumps(result_dict, indent=2)
    
    def run_categoricalvalues_eval(
        self, 
        column: str, 
        allowed_values: List[Any], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, DataFrame]]:
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

        invalid_df = df.filter(~col(column).isin(allowed_values))
        failed_count = invalid_df.count()
        total_count = df.count()
        passed_count = total_count - failed_count

        result_dict = {
            "status": "Success" if failed_count == 0 else "Failed",
            "dqeval_type": "categoricalvalues_eval",
            "column": column,
            "allowed_values": allowed_values,
            "dqeval_total_count": total_count,
            "dqeval_failed_count": failed_count,
            "dqeval_passed_count": passed_count,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id
        }
        if evaluation == "advanced":
            return json.dumps(result_dict, indent=2), invalid_df
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
        from pyspark.sql.functions import mean, stddev, col
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found.")

        if mode == "feature_drift":
            stats = df.select(mean(col(column)).alias("mean"), stddev(col(column)).alias("std")).collect()[0]
            current_mean, current_std = stats["mean"], stats["std"]

            drift_mean = abs(current_mean - reference_stats["mean"])
            drift_std = abs(current_std - reference_stats["std"])
            passed = drift_mean <= tolerance and drift_std <= tolerance

            result_dict = {
                "status": "Success" if passed else "Failed",
                "dqeval_type": "statisticaldistribution_eval",
                "mode": "feature_drift",
                "column": column,
                "dqeval_drift_mean": drift_mean,
                "dqeval_drift_std": drift_std,
                "dqeval_passed": passed,
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id
            }
            return json.dumps(result_dict, indent=2)

        elif mode == "label_balance":
            dist = df.groupBy(column).count()
            total = df.count()
            dist_dict = {row[column]: row["count"] / total for row in dist.collect()}
            max_class_ratio = max(dist_dict.values())
            passed = max_class_ratio <= 0.9

            result_dict = {
                "status": "Success" if passed else "Failed",
                "dqeval_type": "statisticaldistribution_eval",
                "mode": "label_balance",
                "column": column,
                "dqeval_distribution": dist_dict,
                "dqeval_passed": passed,
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
            column: Column name to eval (must be TimestampType).
            freshness_threshold: Freshness threshold as a duration string (e.g., '1d', '12h').

        Returns:
            JSON string with freshness eval results.
        """
        from pyspark.sql.functions import max as spark_max, col
        from datetime import datetime
        df = self.df

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found.")

        spark_type = [f for f in df.schema.fields if f.name == column][0].dataType
        from pyspark.sql.types import TimestampType
        if not isinstance(spark_type, TimestampType):
            raise TypeError(f"Column '{column}' must be of TimestampType.")

        latest_timestamp = df.select(spark_max(col(column))).first()[0]
        freshness_cutoff = datetime.now() - parse_duration_to_timedelta(freshness_threshold)
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
        reference_df: DataFrame, 
        reference_column: str, 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, DataFrame]]:
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
        from pyspark.sql.functions import col
        reference_keys = reference_df.select(reference_column).distinct()
        invalid_rows = self.df.join(reference_keys, self.df[column] == reference_keys[reference_column], "left_anti")
        total = self.df.count()
        failed = invalid_rows.count()
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
        total = self.df.count()

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
        func: Callable[[Any], bool], 
        evaluation: str = "basic"
    ) -> Union[str, Tuple[str, DataFrame]]:
        """
        Run a custom eval using a user-provided function.

        Args:
            column: Column name to apply the function to. If None, applies to each row as a dict.
            func: Callable that returns True if value/row passes, False otherwise.
            evaluation: "basic" returns JSON, "advanced" returns (JSON, DataFrame).

        Returns:
            JSON string (and DataFrame if advanced).
        """
        total = self.df.count()

        if column:
            # column-level UDF
            spark_udf = udf(func, BooleanType())
            failed_df = self.df.filter(~spark_udf(col(column)))
            eval = "custom_eval_column"
        else:
            # row-level UDF: pack entire row into a struct, then as dict
            spark_udf = udf(
                lambda r: func(r.asDict()),
                BooleanType()
            )
            failed_df = self.df.filter(~spark_udf(struct(*self.df.columns)))
            eval = "custom_eval_row"

        failed = failed_df.count()

        result_dict = {
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
            return json.dumps(result_dict, indent=2), failed_df

        return json.dumps(result_dict, indent=2)


