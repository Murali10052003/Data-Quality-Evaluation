import json
import uuid
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from dqeval.dataframe import DqEvalDataFrame
from dqeval.evals.dup_eval import DupEval
from dqeval.evals.empty_eval import EmptyEval
from dqeval.evals.unique_eval import UniqueEval
from dqeval.evals.dtype_eval import DtypeEval
from dqeval.evals.stringformat_eval import StringFormatEval
from dqeval.evals.schema_eval import SchemaValidationEval
from dqeval.evals.range_eval import RangeEval
from dqeval.evals.categoricalvalues_eval import CategoricalValuesEval
from dqeval.evals.statisticaldistribution_eval import StatisticalDistributionEval
from dqeval.evals.datafreshness_eval import DataFreshnessEval
from dqeval.evals.referential_integrity_eval import ReferentialIntegrityEval
from dqeval.evals.rowcount_eval import RowCountEval
from dqeval.evals.custom_eval import CustomEval
from dqeval.evals.unicode_validation_eval import UnicodeValidationEval
import pyspark


class ResultsCollector:
    """
    Collects and aggregates DQEval evaluation results into a unified results table.

    Supports Pandas and Spark engines.

    Results table schema:
    - run_id         : UUID for this evaluation run batch
    - table          : Source table/dataset name
    - dqmethod       : Evaluation method used (e.g., DupEval, EmptyEval)
    - col            : Column(s) evaluated (comma-separated for multi-column evals)
    - status         : 'Success', 'Failed', or 'Error'
    - run_timestamp  : UTC timestamp when the evaluation ran
    - dqevatcount    : Number of records that failed the evaluation

    Usage:
        collector = ResultsCollector(dqevaldf)
        collector.execute_eval('vendor', 'DupEval', {'columns': ['id', 'name']})
        results_df = collector.get_results_dataframe()
    """

    # Maps string method names (used in control tables) to eval classes
    EVAL_MAPPING = {
        'DupEval': DupEval,
        'EmptyEval': EmptyEval,
        'UniqueEval': UniqueEval,
        'DtypeEval': DtypeEval,
        'StringFormatEval': StringFormatEval,
        'SchemaValidationEval': SchemaValidationEval,
        'RangeEval': RangeEval,
        'CategoricalValuesEval': CategoricalValuesEval,
        'StatisticalDistributionEval': StatisticalDistributionEval,
        'DataFreshnessEval': DataFreshnessEval,
        'ReferentialIntegrityEval': ReferentialIntegrityEval,
        'RowCountEval': RowCountEval,
        'CustomEval': CustomEval,
        'UnicodeValidationEval': UnicodeValidationEval,
    }

    def __init__(self, dataframe: DqEvalDataFrame, run_id: Optional[str] = None):
        """
        Initialize the ResultsCollector.

        Args:
            dataframe: DqEvalDataFrame wrapping a Pandas or Spark DataFrame.
            run_id: Optional UUID string to group all evaluations under one run.
                    Auto-generated if not provided.

        Raises:
            TypeError: If dataframe is not a DqEvalDataFrame instance.
        """
        if not isinstance(dataframe, DqEvalDataFrame):
            raise TypeError("Expected a DqEvalDataFrame instance.")

        self.dataframe = dataframe
        self.run_id = run_id or str(uuid.uuid4())
        self._results: List[Dict] = []
        self._error_records: Dict[str, pd.DataFrame] = {}

    def execute_eval(
        self,
        table_name: str,
        dqmethod: str,
        config: Dict,
        collect_errors: bool = True,
    ) -> Dict:
        """
        Execute a single evaluation and collect the result into the results table.

        Args:
            table_name:     Name of the table/dataset being evaluated.
            dqmethod:       Evaluation method name (must be a key in EVAL_MAPPING).
            config:         Configuration dict passed to the evaluation (e.g. {'columns': ['id']}).
            collect_errors: When True, runs in 'advanced' mode to capture failing records.

        Returns:
            Dict representing the result row added to the results table.

        Raises:
            ValueError: If dqmethod is not a supported evaluation name.
        """
        if dqmethod not in self.EVAL_MAPPING:
            raise ValueError(
                f"Unknown dqmethod: '{dqmethod}'. "
                f"Supported methods: {sorted(self.EVAL_MAPPING.keys())}"
            )

        eval_class = self.EVAL_MAPPING[dqmethod]
        eval_instance = eval_class(self.dataframe, config=config, run_id=self.run_id)

        evaluation_mode = "advanced" if collect_errors else "basic"
        raw_result = eval_instance.run(evaluation=evaluation_mode)

        # Advanced mode returns a tuple: (json_string, error_dataframe)
        if isinstance(raw_result, tuple):
            result_json_str, error_df = raw_result
        else:
            result_json_str = raw_result
            error_df = None

        result_dict = json.loads(result_json_str)
        col_str = self._extract_column_info(config)

        row = {
            "run_id": self.run_id,
            "table": table_name,
            "dqmethod": dqmethod,
            "col": col_str,
            "status": result_dict.get("status", "Unknown"),
            "run_timestamp": result_dict.get("run_timestamp"),
            "dqevatcount": result_dict.get("dqeval_failed_count", 0),
        }

        self._results.append(row)

        # Store error records keyed by table + method + column for later retrieval
        if error_df is not None:
            key = self._error_key(table_name, dqmethod, col_str)
            self._error_records[key] = error_df

        return row

    def run_control_table(
        self,
        control_table: Union[pd.DataFrame, "pyspark.sql.DataFrame"],
    ) -> Union[pd.DataFrame, "pyspark.sql.DataFrame"]:
        """
        Execute all evaluations defined in a control table and return the results table.

        Expected control table schema:
        - tablename : str   - Name of the table to evaluate
        - dqmethod  : str   - Evaluation method name (e.g., 'DupEval')
        - config    : dict or JSON string - Config passed to the evaluation

        Args:
            control_table: A Pandas or Spark DataFrame representing the control table.

        Returns:
            Results table as a Pandas or Spark DataFrame (matches the input engine).
        """
        engine = self.dataframe.get_engine()

        # Normalize to Pandas for row iteration
        if engine == "spark":
            control_pd = control_table.toPandas()
        else:
            control_pd = control_table

        for _, row in control_pd.iterrows():
            table_name = str(row["tablename"])
            dqmethod = str(row["dqmethod"])
            config = row.get("config", {})

            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except json.JSONDecodeError:
                    config = {}

            try:
                self.execute_eval(table_name, dqmethod, config)
            except Exception as exc:
                self._results.append({
                    "run_id": self.run_id,
                    "table": table_name,
                    "dqmethod": dqmethod,
                    "col": "N/A",
                    "status": "Error",
                    "run_timestamp": datetime.now(timezone.utc).isoformat(),
                    "dqevatcount": 0,
                })

        return self.get_results_dataframe()

    def get_results_dataframe(self) -> Union[pd.DataFrame, "pyspark.sql.DataFrame"]:
        """
        Return all collected results as a DataFrame.

        Returns:
            Pandas DataFrame (or Spark DataFrame if the source engine is Spark).
        """
        results_df = pd.DataFrame(self._results)
        engine = self.dataframe.get_engine()

        if engine == "spark" and len(results_df) > 0:
            from pyspark.sql import SparkSession
            spark = SparkSession.getActiveSession()
            if spark is not None:
                return spark.createDataFrame(results_df)

        return results_df

    def get_error_records(
        self, table: str, dqmethod: str, col: str
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve the DataFrame of failing records for a specific evaluation.

        Args:
            table:    Table name used in execute_eval.
            dqmethod: Evaluation method name used in execute_eval.
            col:      Column string as stored (comma-separated for multi-column evals).

        Returns:
            Pandas DataFrame of failing records, or None if not found.
        """
        return self._error_records.get(self._error_key(table, dqmethod, col))

    def get_summary(self) -> Dict:
        """
        Return aggregate summary statistics across all evaluations run so far.

        Returns:
            Dict with keys: total_evals, passed, failed, errors, total_failed_records.
        """
        results_df = pd.DataFrame(self._results)
        if results_df.empty:
            return {
                "total_evals": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "total_failed_records": 0,
            }

        return {
            "total_evals": len(results_df),
            "passed": int((results_df["status"] == "Success").sum()),
            "failed": int((results_df["status"] == "Failed").sum()),
            "errors": int((results_df["status"] == "Error").sum()),
            "total_failed_records": int(results_df["dqevatcount"].sum()),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_column_info(self, config: Dict) -> str:
        """Extract column(s) from config and return as a comma-separated string."""
        if "columns" in config:
            cols = config["columns"]
            return ",".join(cols) if isinstance(cols, list) else str(cols)
        if "column" in config:
            return str(config["column"])
        return "N/A"

    def _error_key(self, table: str, dqmethod: str, col: str) -> str:
        """Build the dictionary key used for storing/retrieving error records."""
        return f"{table}__{dqmethod}__{col}"

    def __repr__(self) -> str:
        return (
            f"<ResultsCollector run_id='{self.run_id}' "
            f"engine='{self.dataframe.get_engine()}' "
            f"evals_run={len(self._results)}>"
        )
