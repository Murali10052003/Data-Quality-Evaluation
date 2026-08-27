from dqeval.utils.exceptions import UnsupportedEngineException

class EngineRunner:
    """
    Runs data quality evals using the specified engine (Pandas, Spark, Flink, or Ray).
    """
    def __init__(self, df, engine, run_id=None, columns=None):
        """
        Initialize the EngineRunner.

        Args:
            df: The dataframe to eval.
            engine (str): 'pandas', 'spark', 'flink', or 'ray'.
            run_id (str, optional): Optional run identifier.
        Raises:
            UnsupportedEngineException: If engine is not supported.
        """
        self.run_id = run_id
        if engine == "pandas":
            from dqeval.core.engine.pandas_engine import PandasEngine
            self.engine = PandasEngine(df, self.run_id)
        elif engine == "spark":
            from dqeval.core.engine.spark_engine import SparkEngine
            self.engine = SparkEngine(df, self.run_id)
        elif engine == "ray":
            from dqeval.core.engine.ray_engine import RayEngine
            self.engine = RayEngine(df, self.run_id)
        else:
            raise UnsupportedEngineException(engine)

    def run_dup_eval(self, columns, evaluation="basic"):
        return self.engine.run_dup_eval(columns, evaluation=evaluation)

    def run_empty_eval(self, columns, evaluation="basic"):
        return self.engine.run_empty_eval(columns, evaluation=evaluation)
    
    def run_unique_eval(self, column, evaluation="basic"):
        return self.engine.run_unique_eval(column, evaluation=evaluation)
    
    def run_dtype_eval(self, column, evaluation="basic"):
        return self.engine.run_dtype_eval(column, evaluation=evaluation)
    
    def run_stringformat_eval(self, column, pattern, evaluation="basic"):
        return self.engine.run_stringformat_eval(column, pattern=pattern, evaluation=evaluation)
    
    def run_schemavalidation_eval(self, expected_schema):
        return self.engine.run_schemavalidation_eval(expected_schema)
    
    def run_range_eval(self, column, min_val, max_val, evaluation="basic"):
        return self.engine.run_range_eval(column, min_val, max_val, evaluation=evaluation)
    
    def run_categoricalvalues_eval(self, column, allowed_values, evaluation="basic"):
        return self.engine.run_categoricalvalues_eval(column, allowed_values, evaluation=evaluation)
    
    def run_statisticaldistribution_eval(self, column, mode, reference_stats=None, tolerance=0.05):
        return self.engine.run_statisticaldistribution_eval(column, mode, reference_stats, tolerance)
    
    def run_datafreshness_eval(self, column, freshness_threshold):
        return self.engine.run_datafreshness_eval(column, freshness_threshold)
    
    def run_referential_integrity_eval(self, column, reference_df, reference_column, evaluation="basic"):
        return self.engine.run_referential_integrity_eval(column, reference_df, reference_column, evaluation=evaluation)
    
    def run_rowcount_eval(self, min_rows=None, max_rows=None):
        return self.engine.run_rowcount_eval(min_rows, max_rows)
    
    def run_custom_eval(self, column, func, evaluation="basic"):
        return self.engine.run_custom_eval(column, func, evaluation=evaluation)

    def run_unicode_validation_eval(
        self,
        key_column,
        columns,
        target_df,
        target_columns,
        normalization_form="NFC",
        batch_size=1000,
        evaluation="basic",
    ):
        return self.engine.run_unicode_validation_eval(
            key_column=key_column,
            columns=columns,
            target_df=target_df,
            target_columns=target_columns,
            normalization_form=normalization_form,
            batch_size=batch_size,
            evaluation=evaluation,
        )

    def run_daterange_eval(self, column, min_date, max_date, date_format="%Y-%m-%d", evaluation="basic"):
        return self.engine.run_daterange_eval(column, min_date, max_date, date_format, evaluation=evaluation)

    def run_mojibake_eval(self, column, evaluation="basic"):
        return self.engine.run_mojibake_eval(column, evaluation=evaluation)
