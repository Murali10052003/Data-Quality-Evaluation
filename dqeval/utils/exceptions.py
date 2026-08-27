class DqEvalException(Exception):
    """Base exception for all DqEval-related errors."""
    pass

class ColumnNotFoundException(DqEvalException):
    """Raised when a specified column is not found in the DataFrame."""
    def __init__(self, column):
        message = f"Column '{column}' not found in the DataFrame."
        super().__init__(message)

class UnsupportedEngineException(DqEvalException):
    """Raised when the engine type is not recognized (e.g., not Spark or Pandas)."""
    def __init__(self, engine):
        message = f"Unsupported engine type '{engine}'. Only 'pandas' and 'spark' are supported."
        super().__init__(message)

class ConfigValidationException(DqEvalException):
    """
    Raised when the configuration for a rule is incomplete or invalid.
    Includes expected config format for clarity.
    """
    def __init__(self, message, expected_config=None):
        self.message = message
        self.expected_config = expected_config
        super().__init__(self.__str__())

    def __str__(self):
        if self.expected_config:
            return f"Configuration Error: {self.message}\nExpected Config Format:\n{self.expected_config}"
        return f"Configuration Error: {self.message}"

class RuleExecutionException(DqEvalException):
    """Raised when a rule fails to execute due to internal error."""
    def __init__(self, rule_name, original_exception):
        message = f"Rule '{rule_name}' failed to execute. Reason: {str(original_exception)}"
        super().__init__(message)