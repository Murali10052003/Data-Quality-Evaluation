"""
Environment-based database and pipeline configuration.

All settings are read from environment variables (or a .env file via python-dotenv).
No credentials are hardcoded.
"""

import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; export vars directly if not installed


def _env(key: str, default: str = "") -> str:
    """Read a required env var, falling back to *default*."""
    return os.environ.get(key, default)


@dataclass
class DBConfig:
    """PostgreSQL connection parameters and pipeline settings."""

    host: str = field(default_factory=lambda: _env("DQ_DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(_env("DQ_DB_PORT", "5432")))
    name: str = field(default_factory=lambda: _env("DQ_DB_NAME", "postgres"))
    user: str = field(default_factory=lambda: _env("DQ_DB_USER", "postgres"))
    password: str = field(default_factory=lambda: _env("DQ_DB_PASSWORD", ""))

    # Schema that owns dq_control, dq_results and (by default) the business tables
    schema: str = field(default_factory=lambda: _env("DQ_DB_SCHEMA", "public"))

    # Metadata table names
    control_table: str = field(
        default_factory=lambda: _env("DQ_CONTROL_TABLE", "dq_control")
    )
    results_table: str = field(
        default_factory=lambda: _env("DQ_RESULTS_TABLE", "dq_results")
    )

    # Directory where per-table failed-row JSONL log files are written.
    # Each run gets its own sub-folder: <failed_log_dir>/<run_id>/<table>.jsonl
    failed_log_dir: str = field(
        default_factory=lambda: _env("DQ_FAILED_LOG_DIR", "failed_logs")
    )

    # Logging level for the pipeline (DEBUG | INFO | WARNING | ERROR)
    log_level: str = field(default_factory=lambda: _env("DQ_LOG_LEVEL", "INFO"))

    @property
    def url(self) -> str:
        """SQLAlchemy connection URL (password never logged)."""
        return (
        f"postgresql+psycopg://{quote_plus(self.user)}:{quote_plus(self.password)}"
        f"@{self.host}:{self.port}/{self.name}?sslmode=require"
    )

    def __repr__(self) -> str:  # keep password out of logs / tracebacks
        return (
            f"DBConfig(host={self.host!r}, port={self.port}, "
            f"name={self.name!r}, user={self.user!r}, schema={self.schema!r}, "
            f"control_table={self.control_table!r}, results_table={self.results_table!r}, "
            f"failed_log_dir={self.failed_log_dir!r})"
        )
