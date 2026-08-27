from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator

class RangeEval(BaseDQEval):
    """
    Range Check Rule:
    Verifies that values in a numeric column fall within specified bounds.

    Example config:
    {
        "column": "age",
        "min": 0,
        "max": 120
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")
        min_val = self.config.get("min")
        max_val = self.config.get("max")

        if column is None or min_val is None or max_val is None:
            raise ValueError("'column', 'min', and 'max' must be specified in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        # Column existence check for pandas/spark
        if engine not in {"ray", "flink"}:
            if column not in df.columns:
                raise ColumnNotFoundException(column)

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_range_eval(column, min_val, max_val, evaluation=evaluation)
    
    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),  # Required: Column name to validate range
            "min": ((int, float), True),  # Required: Minimum allowable value
            "max": ((int, float), True)   # Required: Maximum allowable value
        }
