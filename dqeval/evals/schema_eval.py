from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.config_validator import ConfigValidator

class SchemaValidationEval(BaseDQEval):
    """
    Schema Validation Rule:
    Ensures required columns exist and data types match expectations.

    Example config:
    {
        "expected_schema": {
            "id": "int",
            "timestamp": "datetime64[ns]",
            "price": "float"
        }
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        expected_schema = self.config.get("expected_schema")
        if not expected_schema:
            raise ValueError("'expected_schema' must be provided in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_schemavalidation_eval(expected_schema)
    
    @classmethod
    def expected_config(cls):
        return {
            "expected_schema": (dict, True)  # Required: A dictionary of column names with their expected data types
        }
