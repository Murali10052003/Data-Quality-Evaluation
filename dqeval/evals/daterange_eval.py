from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator


class DateRangeEval(BaseDQEval):
    """
    Date Range Check:
    Verifies that date/datetime values in a column fall within a specified range.

    Example config:
    {
        "column": "order_date",
        "min_date": "2020-01-01",
        "max_date": "2025-12-31",
        "date_format": "%Y-%m-%d"
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")
        min_date = self.config.get("min_date")
        max_date = self.config.get("max_date")
        date_format = self.config.get("date_format", "%Y-%m-%d")

        if not column or not min_date or not max_date:
            raise ValueError("'column', 'min_date', and 'max_date' must be specified in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        if engine not in {"ray", "flink"}:
            if column not in df.columns:
                raise ColumnNotFoundException(column)

        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_daterange_eval(column, min_date, max_date, date_format, evaluation=evaluation)

    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),
            "min_date": (str, True),
            "max_date": (str, True),
            "date_format": (str, False),
        }
