import re
import pandas as pd

def parse_duration_to_timedelta(duration_str):
    """
    Parses compact duration formats like '1d', '2h', '-7d' , '30m' into pandas.Timedelta.

    Allowed suffixes:
    - 'd' for days
    - 'h' for hours
    - 'm' for minutes
    """
    duration_str = duration_str.strip().lower()
    match = re.fullmatch(r"(-?\d+)([dhm])", duration_str)

    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Use format like '1d', '2h', or '30m'."
        )

    value, unit = match.groups()
    value = int(value)

    unit_map = {
        "d": "days",
        "h": "hours",
        "m": "minutes",
    }

    return pd.Timedelta(**{unit_map[unit]: value})
