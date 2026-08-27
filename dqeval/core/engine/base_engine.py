from abc import ABC, abstractmethod

class BaseEngine(ABC):
    """
    Abstract base class for data quality engines.
    """

    def __init__(self, df,run_id=None):
        """
        Args:
            df: The dataframe to operate on.
            run_id: Optional identifier for the run.
        """
        self.df = df
        self.run_id = run_id
