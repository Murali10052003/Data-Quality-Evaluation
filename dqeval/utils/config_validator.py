from dqeval.utils.exceptions import ConfigValidationException

class ConfigValidator:
    """
    Utility class to validate configuration dictionaries against expected structure.
    """

    @staticmethod
    def validate(config, expected_config):
        """
        Validates the config dictionary against expected keys and types.

        Parameters:
        - config (dict): User-provided config.
        - expected_config (dict): Expected format like {key: (type, required)}

        Raises:
        - ConfigValidationException: If the config is missing required fields or has incorrect types.
        """
        for key, (expected_type, required) in expected_config.items():
            # 1) Missing required key?
            if required and key not in config:
                raise ConfigValidationException(
                    f"Missing required config key: '{key}'",
                    expected_config=expected_config
                )

            # 2) If key is present...
            if key in config:
                value = config[key]

                # 2a) If not required and explicitly set to None, accept it
                if not required and value is None:
                    continue

                # 2b) Otherwise enforce type-check
                if not isinstance(value, expected_type):
                    raise ConfigValidationException(
                        f"Invalid type for '{key}'. "
                        f"Expected {expected_type.__name__}, got {type(value).__name__}",
                        expected_config=expected_config
                    )
            # else: key is absent but not required → OK
