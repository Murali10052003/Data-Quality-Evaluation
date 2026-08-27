from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator

class DtypeEval(BaseDQEval):
    """
    Data Type Match Check Rule:
    Ensures that the specified column(s) match the expected data types.
    Supports Pandas, Spark DataFrames and Ray.
    
    Configuration example:
    {
        "columns": {
            "age": "int",
            "name": "string"
        }
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column_types = self.config.get("columns")
        if not column_types or not isinstance(column_types, dict):
            raise ValueError("'columns' must be a dictionary of column: expected_dtype pairs.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()
        if engine not in {"ray", "flink"}:
            for column in column_types.keys():
                if column not in df.columns:
                    raise ColumnNotFoundException(column)

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_dtype_eval(column_types, evaluation=evaluation)
    
    @classmethod
    def expected_config(cls):
        return {
            "columns": (dict, True)  # Required: {"column_name": "expected_dtype"}
        }