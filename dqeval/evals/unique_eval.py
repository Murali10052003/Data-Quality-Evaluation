from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator

class UniqueEval(BaseDQEval):
    """
    Unique Value Check Rule:
    Ensures that the values in the specified column(s) are unique.
    Supports both Pandas and Spark DataFrames.
    
    Configuration example:
    {
        "columns": ["user_id"]
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        
        columns = self.config.get("columns")
        if not columns:
            raise ValueError("'columns' must be specified in the config.")

        if len(columns) != 1:
            raise ValueError("Unique check must be run on exactly one column.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()
        if engine not in {"ray", "flink"}:
            column = columns[0]
            if column not in df.columns:
                raise ColumnNotFoundException(column)

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_unique_eval(columns, evaluation=evaluation)
    
    @classmethod
    def expected_config(cls):
        return {
            "columns": (list, True),  # List of columns to check uniqueness (required)
        }