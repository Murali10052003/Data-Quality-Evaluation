import uuid
from abc import ABC, abstractmethod
from dqeval.dataframe import DqEvalDataFrame
from dqeval.utils.exceptions import ConfigValidationException

class BaseDQEval(ABC):
    """
    Abstract base class for all data quality evaluations.
    Provides a common interface and shared initialization logic.
    """

    def __init__(self, df, config=None, run_id=None):
        """
        Initialize with a DataFrame and optional configuration and run_id.

        Parameters:
        - df: DqEvalDataFrame
        - config: dict, optional configuration for the check
        - run_id: Optional[str], UUID string for tracking the run

        Raises:
        - TypeError: if df is not a DqEvalDataFrame
        - ValueError: if run_id is provided but is not a valid UUID
        """
        if not isinstance(df, DqEvalDataFrame):
            raise TypeError("Expected a DqEvalDataFrame instance.")
        
        self.qdf = df # Wrapping in unified DqEvalDataFrame
        self.config = config or {}

        if run_id is not None:
            try:
                uuid_obj = uuid.UUID(str(run_id))
                self.run_id = str(uuid_obj)  # store normalized UUID
            except (ValueError, AttributeError, TypeError):
                raise ValueError("run_id must be a valid UUID string if provided.")
        else:
            self.run_id = None

    @abstractmethod
    def run(self, evaluation="basic"):
        """
        Abstract method to be implemented by each data quality rule class.

        Parameters:
        - evaluation (str): One of "basic" or "advanced". Determines output detail level.

        Returns:
        - Dictionary or dict + DataFrame depending on evaluation level.
        """
        pass

    @classmethod
    @abstractmethod
    def expected_config(cls):
        """
        Returns expected configuration schema as a dictionary:
        {
            "param_name": (expected_type, required: bool)
        }
        """
        pass

    def validate_config(self):
        schema = self.expected_config()
        for key, (expected_type, required) in schema.items():
            if required and key not in self.config:
                raise ConfigValidationException(f"Missing required config key: '{key}'")

            if key in self.config and not isinstance(self.config[key], expected_type):
                raise ConfigValidationException(
                    f"Config key '{key}' expected type {expected_type.__name__}, got {type(self.config[key]).__name__}"
                )
