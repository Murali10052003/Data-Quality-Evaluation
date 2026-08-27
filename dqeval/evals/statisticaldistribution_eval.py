from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator

class StatisticalDistributionEval(BaseDQEval):
    """
    Statistical Distribution Check:
    - Feature Drift: Compares mean/std of feature with training stats.
    - Label Balance: Checks class distribution balance.

    Configuration example:
    {
        "column": "feature",
        "mode": "feature_drift",  # or "label_balance"
        "reference_stats": {
            "mean": 0.5,
            "std": 0.1
        },
        "tolerance": 0.05
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")
        mode = self.config.get("mode")
        reference_stats = self.config.get("reference_stats", {})
        tolerance = self.config.get("tolerance", 0.05)

        if not column or not mode:
            raise ValueError("Both 'column' and 'mode' are required in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()
        if engine not in {"ray", "flink"}:
            if column not in df.columns:
                raise ColumnNotFoundException(column)

        # Pass columns for flink, else None
        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_statisticaldistribution_eval(
            column=column,
            mode=mode,
            reference_stats=reference_stats,
            tolerance=tolerance
        )
    
    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),  # Column to check (required)
            "mode": (str, True),  # Mode of check (required: feature_drift or label_balance)
            "reference_stats": (dict, False),  # Reference stats for feature drift (optional)
            "tolerance": (float, False)  # Tolerance for feature drift comparison (optional)
        }
