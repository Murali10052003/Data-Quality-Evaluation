from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator

class StringFormatEval(BaseDQEval):
    r"""
    String Format Check Rule:
    Validates string columns against a specified regex pattern.

    Configuration example:
    {
        "column": "email",
        "pattern": "^[a-z0-9]+@[a-z]+\.[a-z]{2,3}$"
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")
        pattern = self.config.get("pattern")
        if not column or not pattern:
            raise ValueError("Both 'column' and 'pattern' must be specified in the config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()
        if engine not in {"ray", "flink"}:
            if column not in df.columns:
                raise ColumnNotFoundException(column)
        
        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_stringformat_eval(column, pattern, evaluation=evaluation)
    
    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),  # Column to check (required)
            "pattern": (str, True),  # Regex pattern to validate string format (required)
        }