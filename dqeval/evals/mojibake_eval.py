import re

from dqeval.base import BaseDQEval
from dqeval.core.engine_runner import EngineRunner
from dqeval.utils.exceptions import ColumnNotFoundException
from dqeval.utils.config_validator import ConfigValidator


class MojibakeEval(BaseDQEval):
    """
    Mojibake Detection Check:
    Detects mojibake (garbled text from encoding mismatches) in string columns.

    Mojibake occurs when multi-byte UTF-8 sequences are decoded as a single-byte
    encoding (Latin-1 / Windows-1252), producing patterns like "Ã©" instead of "é".

    Example config:
    {
        "column": "customer_name"
    }
    """

    def run(self, evaluation="basic"):
        ConfigValidator.validate(self.config, self.expected_config())
        column = self.config.get("column")

        if not column:
            raise ValueError("'column' must be specified in config.")

        df = self.qdf.get_df()
        engine = self.qdf.get_engine()

        if engine not in {"ray", "flink"}:
            if column not in df.columns:
                raise ColumnNotFoundException(column)

        columns_arg = self.qdf.columns if engine in {"flink"} else None
        runner = EngineRunner(df, engine, run_id=self.run_id, columns=columns_arg)
        return runner.run_mojibake_eval(column, evaluation=evaluation)

    @classmethod
    def expected_config(cls):
        return {
            "column": (str, True),
        }
