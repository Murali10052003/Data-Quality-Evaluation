from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.config_validator import ConfigValidator

class RowCountEval(BaseDQEval):
    """
    Row Count Check:
    Ensures the dataset meets minimum and/or maximum row count requirements.
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        min_rows = self.config.get("min")
        max_rows = self.config.get("max")

        if min_rows is None and max_rows is None:
            raise ValueError("At least one of 'min' or 'max' must be specified in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_rowcount_eval(min_rows=min_rows, max_rows=max_rows)
    
    @classmethod
    def expected_config(cls):
        return {
            "min": (int, False),
            "max": (int, False)
        }
