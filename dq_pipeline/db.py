"""
Database helpers: engine creation, parameterised reads, and bulk inserts.

All SQL identifiers are double-quoted to handle mixed-case names safely.
"""

import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import DBConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def get_engine(config: DBConfig) -> Engine:
    """Create and return a SQLAlchemy engine.

    ``pool_pre_ping=True`` drops stale connections automatically.
    TCP keepalives prevent Azure PostgreSQL from dropping long-running
    connections. ``statement_timeout=0`` disables the server-side query
    kill timeout so large table reads are not terminated mid-transfer.
    """
    connect_args = {
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "options": "-c statement_timeout=0",
    }
    engine = create_engine(config.url, pool_pre_ping=True, connect_args=connect_args)
    logger.info(
        "Engine created → %s:%s / %s (schema: %s)",
        config.host, config.port, config.name, config.schema,
    )
    return engine


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def read_query(engine: Engine, query: str, params: dict | None = None) -> pd.DataFrame:
    """Execute *query* and return results as a Pandas DataFrame."""
    logger.debug("SQL → %s  params=%s", query.strip(), params)
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def read_table(engine: Engine, schema: str, table: str) -> pd.DataFrame:
    """SELECT * from *schema*.*table*."""
    query = f'SELECT * FROM "{schema}"."{table}"'
    logger.info("Reading %s.%s …", schema, table)
    return read_query(engine, query)


def read_table_chunked(
    engine: Engine,
    schema: str,
    table: str,
    chunksize: int = 500_000,
):
    """Yield *chunksize*-row Pandas DataFrames for *schema*.*table*.

    Never loads the full table into RAM at once — each chunk is returned
    as an independent DataFrame so the caller can process and discard it.

    Usage::
        for chunk in read_table_chunked(engine, "public", "employee", 500_000):
            process(chunk)
    """
    query = f'SELECT * FROM "{schema}"."{table}"'
    logger.info("Streaming %s.%s in chunks of %d …", schema, table, chunksize)
    with engine.connect() as conn:
        yield from pd.read_sql(text(query), conn, chunksize=chunksize)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def insert_dataframe(
    engine: Engine,
    df: pd.DataFrame,
    schema: str,
    table: str,
    if_exists: str = "append",
) -> None:
    """Append *df* into *schema*.*table*.

    Uses SQLAlchemy's ``method='multi'`` for efficient batch inserts.
    Raises on any database error so the caller can handle it.
    """
    if df.empty:
        logger.warning("insert_dataframe: empty DataFrame – nothing written to %s.%s.", schema, table)
        return

    logger.info("Inserting %d row(s) into %s.%s …", len(df), schema, table)
    if "run_timestamp" in df.columns:
        df = df.copy()
        # ISO strings from the engines must become tz-aware datetimes for TIMESTAMPTZ.
        df["run_timestamp"] = pd.to_datetime(df["run_timestamp"], utc=True)
    df.to_sql(
        name=table,
        con=engine,
        schema=schema,
        if_exists=if_exists,
        index=False,
        method="multi",
    )
    logger.info("Insert complete → %s.%s", schema, table)
