class DqEvalDataFrame:
    """
    Wrapper for Pandas, Spark, and Ray DataFrames to provide a unified interface.
    """
    def __init__(self, df, columns=None):
        """
        Args:
            df: A pandas.DataFrame, pyspark.sql.DataFrame, or ray.data.Dataset.
            columns: Optional list of column names.
        Raises:
            TypeError: If df is not a supported DataFrame type.
        """
        self.df = df
        self.columns = columns
        self.engine = self._infer_engine()

    def _infer_engine(self):
        import pandas as pd

        try:
            from pyspark.sql import DataFrame as SparkDF
        except ImportError:
            SparkDF = None
        try:
            # Add support for Spark Connect DataFrame
            from pyspark.sql.connect.dataframe import DataFrame as SparkConnectDF
        except ImportError:
            SparkConnectDF = None
        try:
            from ray.data import Dataset as RayDataset
        except ImportError:
            RayDataset = None

        if isinstance(self.df, pd.DataFrame):
            return 'pandas'
        if (SparkDF and isinstance(self.df, SparkDF)) or (SparkConnectDF and isinstance(self.df, SparkConnectDF)):
            return 'spark'
        if RayDataset and isinstance(self.df, RayDataset):
            return 'ray'

        raise TypeError(
            f"Unsupported dataframe type: {type(self.df)}. "
            "Supported types: pandas.DataFrame, pyspark.sql.DataFrame, pyspark.sql.connect.dataframe.DataFrame, "
            "ray.data.Dataset"
        )

    def is_pandas(self):
        return self.engine == 'pandas'

    def is_spark(self):
        return self.engine == 'spark'

    def is_ray(self):
        return self.engine == 'ray'    

    def get_df(self):
        return self.df

    def get_engine(self):
        return self.engine

    def __repr__(self):
        return f"<DqEvalDataFrame engine='{self.engine}' type={type(self.df).__name__}>"

