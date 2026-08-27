from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
import pandas as pd
from dqeval.utils.config_validator import ConfigValidator

class ReferentialIntegrityEval(BaseDQEval):
    """
    Referential Integrity Check:
    Ensures values in a column exist in a reference dataset column.

    Example config:
    {
        "column": "user_id",
        "reference_df": reference_dataframe,
        "reference_column": "user_id"
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")
        reference_df = self.config.get("reference_df")
        reference_column = self.config.get("reference_column")

        if not all([column, reference_df is not None, reference_column]):
            raise ValueError("Config must include 'column', 'reference_df', and 'reference_column'.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        # Ensure both are same kind (local imports for optional dependencies)
        if isinstance(df, pd.DataFrame):
            if not isinstance(reference_df, pd.DataFrame):
                raise TypeError("Expected both df and reference_df to be pandas DataFrames.")
        else:
            try:
                from pyspark.sql import DataFrame as SparkDF
            except ImportError:
                SparkDF = None
            try:
                from pyspark.sql.connect.dataframe import DataFrame as SparkConnectDF
            except ImportError:
                SparkConnectDF = None
            try:
                from ray.data import Dataset as RayDataset
            except ImportError:
                RayDataset = None

            if SparkDF and isinstance(df, SparkDF):
                if not (SparkDF and isinstance(reference_df, SparkDF)):
                    raise TypeError("Expected both df and reference_df to be Spark DataFrames.")
            elif SparkConnectDF and isinstance(df, SparkConnectDF):
                if not (SparkConnectDF and isinstance(reference_df, SparkConnectDF)):
                    raise TypeError("Expected both df and reference_df to be Spark Connect DataFrames.")
            elif RayDataset and isinstance(df, RayDataset):
                if not (RayDataset and isinstance(reference_df, RayDataset)):
                    raise TypeError("Expected both df and reference_df to be Ray Datasets.")
            else:
                raise TypeError("Unsupported dataframe type for referential integrity check.")

        if engine not in {"ray", "flink"}:
            if column not in getattr(df, "columns", []):
                raise ColumnNotFoundException(column)
            if reference_column not in getattr(reference_df, "columns", []):
                raise ColumnNotFoundException(reference_column)

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_referential_integrity_eval(column, reference_df, reference_column, evaluation)
    
    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),  # Required: Column name in the main dataframe
            "reference_df": (object, True),  # Required: The reference dataframe
            "reference_column": (str, True)  # Required: Column name in the reference dataframe
        }
