import ast
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import psycopg
import pandas as pd
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text

# Load .env from project root (one level above backend/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _env(k: str, d: str = "") -> str:
    return os.environ.get(k, d)


_host = _env("DQ_DB_HOST", "localhost")
_port = int(_env("DQ_DB_PORT", "5432"))
_name = _env("DQ_DB_NAME", "postgres")
_ssl  = _env("DQ_DB_SSLMODE", "require")
_user = _env("DQ_DB_USER")

SCHEMA         = _env("DQ_DB_SCHEMA", "public")
CONTROL_TABLE  = _env("DQ_CONTROL_TABLE", "dq_control")
RESULTS_TABLE  = _env("DQ_RESULTS_TABLE", "dq_results")
PIPELINE_DIR   = _env("DQ_PIPELINE_DIR", str(Path(__file__).resolve().parent.parent))
FAILED_LOG_DIR = _env("DQ_FAILED_LOG_DIR", str(Path(PIPELINE_DIR) / "failed_logs"))

# --- Token cache: Azure tokens expire in ~75 min; refresh via azure-identity when needed ---
# DefaultAzureCredential chains: Managed Identity in Azure, AzureCliCredential ('az login') locally.
_credential = DefaultAzureCredential()
_token_cache: dict = {"token": None, "expires_at": 0.0}

def _get_token() -> str:
    """Return a valid Azure Entra token for Postgres AAD auth, refreshing when needed."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    access_token = _credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    _token_cache["token"] = access_token.token
    _token_cache["expires_at"] = access_token.expires_on - 300
    logger.info("Azure DB token refreshed, valid until %s",
                time.strftime("%H:%M:%S", time.localtime(_token_cache["expires_at"])))
    return access_token.token

def _create_db_connection():
    """Creator passed to SQLAlchemy so every new pool connection uses a fresh token."""
    return psycopg.connect(
        host=_host,
        port=_port,
        dbname=_name,
        user=_user,
        password=_get_token(),
        sslmode=_ssl,
    )

engine = create_engine("postgresql+psycopg://", creator=_create_db_connection, pool_pre_ping=True)

app = FastAPI(title="DQ Eval API", version="1.0.0")
# Extra deployed frontend origin(s), comma-separated (e.g. the Static Web App hostname)
_extra_origins = [o.strip() for o in _env("DQ_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3030", "http://127.0.0.1:3030",
                   "http://localhost:5173", "http://127.0.0.1:5173"] + _extra_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for running pipeline processes
_run_processes: dict[str, subprocess.Popen] = {}
_run_logs: dict[str, list[str]] = {}


# ── Pydantic models ────────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    schema_name: str
    table_name: str
    dqmethod: str
    config: dict
    is_active: bool = True


class RulePatch(BaseModel):
    is_active: bool


class LambdaValidate(BaseModel):
    func_str: str


class RunRequest(BaseModel):
    schema_name: Optional[str] = None
    table_name: Optional[str] = None


# ── DB helper ──────────────────────────────────────────────────────────────────

def run_query(sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


# ── Schema / Table / Column discovery ─────────────────────────────────────────

@app.get("/api/schemas")
def get_schemas():
    rows = run_query(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name NOT IN ('information_schema','pg_catalog','pg_toast') "
        "ORDER BY schema_name"
    )
    return [r["schema_name"] for r in rows]


@app.get("/api/tables")
def get_tables(schema: str = "public"):
    rows = run_query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_type = 'BASE TABLE' ORDER BY table_name",
        {"schema": schema},
    )
    return [r["table_name"] for r in rows]


@app.get("/api/columns")
def get_columns(schema: str = "public", table: str = ""):
    if not table:
        raise HTTPException(400, "table parameter required")
    rows = run_query(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = :schema AND table_name = :table ORDER BY ordinal_position",
        {"schema": schema, "table": table},
    )
    return rows


# ── Rules CRUD ─────────────────────────────────────────────────────────────────

@app.get("/api/rules")
def get_rules(schema: str = "", table: str = "", active_only: bool = False):
    where, params = [], {}
    if schema:
        where.append("schema_name = :schema")
        params["schema"] = schema
    if table:
        where.append("table_name = :table")
        params["table"] = table
    if active_only:
        where.append("is_active = TRUE")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return run_query(
        f'SELECT * FROM "{SCHEMA}"."{CONTROL_TABLE}" {clause} ORDER BY created_at DESC',
        params,
    )


@app.post("/api/rules", status_code=201)
def create_rule(body: RuleCreate):
    with engine.begin() as conn:
        if body.is_active:
            existing = conn.execute(
                text(
                    f'SELECT control_id FROM "{SCHEMA}"."{CONTROL_TABLE}" '
                    "WHERE schema_name = :sn AND table_name = :tn AND dqmethod = :dm "
                    "AND is_active = TRUE AND config = CAST(:cfg AS jsonb)"
                ),
                {
                    "sn": body.schema_name,
                    "tn": body.table_name,
                    "dm": body.dqmethod,
                    "cfg": json.dumps(body.config),
                },
            ).fetchone()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"An identical active rule already exists for "
                        f"{body.schema_name}.{body.table_name} / {body.dqmethod} "
                        f"(control_id={existing[0]})."
                    ),
                )
        result = conn.execute(
            text(
                f'INSERT INTO "{SCHEMA}"."{CONTROL_TABLE}" '
                "(schema_name, table_name, dqmethod, config, is_active) "
                "VALUES (:sn, :tn, :dm, CAST(:cfg AS jsonb), :ia) RETURNING control_id"
            ),
            {
                "sn": body.schema_name,
                "tn": body.table_name,
                "dm": body.dqmethod,
                "cfg": json.dumps(body.config),
                "ia": body.is_active,
            },
        )
        row = result.fetchone()
        return {"control_id": row[0]}


@app.patch("/api/rules/{control_id}")
def patch_rule(control_id: int, body: RulePatch):
    with engine.begin() as conn:
        conn.execute(
            text(
                f'UPDATE "{SCHEMA}"."{CONTROL_TABLE}" '
                "SET is_active = :ia WHERE control_id = :id"
            ),
            {"ia": body.is_active, "id": control_id},
        )
    return {"ok": True}


@app.delete("/api/rules/{control_id}")
def delete_rule(control_id: int):
    with engine.begin() as conn:
        conn.execute(
            text(f'DELETE FROM "{SCHEMA}"."{CONTROL_TABLE}" WHERE control_id = :id'),
            {"id": control_id},
        )
    return {"ok": True}


# ── Lambda validation (AST-only, never executes) ───────────────────────────────

@app.post("/api/validate-lambda")
def validate_lambda(body: LambdaValidate):
    try:
        tree = ast.parse(body.func_str.strip(), mode="eval")
        if not isinstance(tree.body, ast.Lambda):
            return {"valid": False, "error": "Expression must be a lambda"}
        return {"valid": True, "error": None}
    except SyntaxError as exc:
        return {"valid": False, "error": str(exc)}


# ── Pipeline runner ────────────────────────────────────────────────────────────

@app.post("/api/run")
def run_pipeline(body: RunRequest):
    run_id = str(uuid.uuid4())
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "DQ_RUN_ID": run_id}
    # Pass a fresh Azure token so the subprocess can connect to the DB
    env["DQ_DB_PASSWORD"] = _get_token()
    if body.schema_name:
        env["DQ_FILTER_SCHEMA"] = body.schema_name
    if body.table_name:
        env["DQ_FILTER_TABLE"] = body.table_name
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=PIPELINE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _run_processes[run_id] = proc
    _run_logs[run_id] = []
    return {"run_id": run_id}


@app.get("/api/run/{run_id}/status")
def run_status(run_id: str):
    proc = _run_processes.get(run_id)
    if not proc:
        raise HTTPException(404, "Run not found")
    # Drain available stdout without blocking
    if proc.stdout:
        for line in iter(lambda: proc.stdout.readline() if proc.poll() is not None or proc.stdout.readable() else "", ""):
            if not line:
                break
            _run_logs[run_id].append(line.rstrip())
    rc = proc.poll()
    return {
        "status": "running" if rc is None else ("complete" if rc == 0 else "failed"),
        "log_tail": _run_logs[run_id][-200:],
        "returncode": rc,
    }


# ── Results ────────────────────────────────────────────────────────────────────

def _build_results_filter(run_id: str, from_ts: str, to_ts: str) -> tuple[str, dict]:
    """Build WHERE clause for results filtering by run_id and date range."""
    where, params = [], {}
    if run_id:
        where.append("run_id = :run_id")
        params["run_id"] = run_id
    if from_ts:
        where.append("run_timestamp >= :fts")
        params["fts"] = from_ts
    if to_ts:
        where.append("run_timestamp <= :tts")
        params["tts"] = to_ts
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params


@app.get("/api/results/summary")
def results_summary(
    run_id: str = "",
    from_ts: str = Query("", alias="from"),
    to_ts: str = Query("", alias="to"),
):
    clause, params = _build_results_filter(run_id, from_ts, to_ts)
    rows = run_query(
        f'SELECT status, dqmethod, COUNT(*) AS cnt '
        f'FROM "{SCHEMA}"."{RESULTS_TABLE}" {clause} GROUP BY status, dqmethod',
        params,
    )
    total   = sum(r["cnt"] for r in rows)
    success = sum(r["cnt"] for r in rows if r["status"] == "Success")
    failed  = sum(r["cnt"] for r in rows if r["status"] == "Failed")
    error   = sum(r["cnt"] for r in rows if r["status"] == "Error")

    by_method: dict[str, dict] = {}
    for r in rows:
        m = r["dqmethod"]
        if m not in by_method:
            by_method[m] = {"Success": 0, "Failed": 0, "Error": 0}
        by_method[m][r["status"]] = r["cnt"]

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "error": error,
        "by_method": [{"dqmethod": k, **v} for k, v in by_method.items()],
    }


@app.get("/api/results/trend")
def results_trend(
    run_id: str = "",
    from_ts: str = Query("", alias="from"),
    to_ts: str = Query("", alias="to"),
    bucket: str = "hour",
):
    """Time-bucketed aggregation for trend charts. bucket: hour, day, week."""
    valid_buckets = {"hour", "day", "week"}
    if bucket not in valid_buckets:
        raise HTTPException(400, f"bucket must be one of {valid_buckets}")
    clause, params = _build_results_filter(run_id, from_ts, to_ts)
    rows = run_query(
        f"SELECT DATE_TRUNC(:bucket, run_timestamp) AS ts, status, COUNT(*) AS cnt "
        f'FROM "{SCHEMA}"."{RESULTS_TABLE}" {clause} '
        f"GROUP BY ts, status ORDER BY ts",
        {**params, "bucket": bucket},
    )
    # Pivot into [{ts, Success, Failed, Error}, ...]
    buckets: dict[str, dict] = {}
    for r in rows:
        t = str(r["ts"])
        if t not in buckets:
            buckets[t] = {"ts": t, "Success": 0, "Failed": 0, "Error": 0}
        buckets[t][r["status"]] = r["cnt"]
    return list(buckets.values())


@app.get("/api/results")
def get_results(
    run_id: str = "",
    table: str = "",
    method: str = "",
    status: str = "",
    from_ts: str = Query("", alias="from"),
    to_ts: str = Query("", alias="to"),
    page: int = 1,
    page_size: int = 50,
):
    where, params = [], {}
    if run_id:  where.append("run_id = :run_id");       params["run_id"] = run_id
    if table:   where.append("table_name = :table");    params["table"]  = table
    if method:  where.append("dqmethod = :method");     params["method"] = method
    if status:  where.append("status = :status");       params["status"] = status
    if from_ts: where.append("run_timestamp >= :fts");  params["fts"]    = from_ts
    if to_ts:   where.append("run_timestamp <= :tts");  params["tts"]    = to_ts
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * page_size

    rows = run_query(
        f'SELECT * FROM "{SCHEMA}"."{RESULTS_TABLE}" {clause} '
        f"ORDER BY run_timestamp DESC LIMIT {page_size} OFFSET {offset}",
        params,
    )
    total_rows = run_query(
        f'SELECT COUNT(*) AS cnt FROM "{SCHEMA}"."{RESULTS_TABLE}" {clause}', params
    )
    return {"rows": rows, "total": total_rows[0]["cnt"], "page": page}


@app.get("/api/runs")
def list_runs():
    return run_query(
        f'SELECT run_id, MIN(run_timestamp) AS started_at, '
        f"COUNT(*) AS total, "
        f"SUM(CASE WHEN status='Failed' THEN 1 ELSE 0 END) AS failed "
        f'FROM "{SCHEMA}"."{RESULTS_TABLE}" '
        f"GROUP BY run_id ORDER BY started_at DESC LIMIT 50"
    )


# ── Failed rows (from JSONL files) ────────────────────────────────────────────

@app.get("/api/failed-rows")
def get_failed_rows(
    run_id: str = "",
    table: str = "",
    method: str = "",
    col: str = "",
    page: int = 1,
    page_size: int = 100,
):
    if not run_id or not table:
        raise HTTPException(400, "run_id and table are required")
    path = Path(FAILED_LOG_DIR) / run_id / f"{table}.jsonl"
    if not path.exists():
        return {"rows": [], "total": 0, "page": page}
    # Stream through the file, count matching records, return only the requested page
    total = 0
    results = []
    offset = (page - 1) * page_size
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if method and rec.get("dqmethod") != method:
                continue
            if col and rec.get("col") != col:
                continue
            if total >= offset and len(results) < page_size:
                results.append(rec)
            total += 1
    return {"rows": results, "total": total, "page": page}


@app.get("/api/failed-rows/export")
def export_failed_rows(run_id: str = "", table: str = "", method: str = ""):
    if not run_id or not table:
        raise HTTPException(400, "run_id and table are required")
    path = Path(FAILED_LOG_DIR) / run_id / f"{table}.jsonl"
    if not path.exists():
        raise HTTPException(404, "Log file not found")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if method and rec.get("dqmethod") != method:
                continue
            flat = {
                **rec.get("failed_row", {}),
                "dqmethod": rec.get("dqmethod"),
                "col": rec.get("col"),
                "run_id": rec.get("run_id"),
            }
            rows.append(flat)
    df = pd.DataFrame(rows)
    csv_content = df.to_csv(index=False)

    def _iter():
        yield csv_content

    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}_failed.csv"},
    )


@app.get("/api/failed-rows/download-jsonl")
def download_failed_jsonl(run_id: str = "", table: str = ""):
    """Download the raw JSONL log file for a specific run + table."""
    if not run_id or not table:
        raise HTTPException(400, "run_id and table are required")
    path = Path(FAILED_LOG_DIR) / run_id / f"{table}.jsonl"
    if not path.exists():
        raise HTTPException(404, "Log file not found")
    return FileResponse(
        path,
        media_type="application/jsonl",
        filename=f"{table}_failed_{run_id[:8]}.jsonl",
    )


@app.get("/api/failed-logs/runs")
def list_failed_log_runs():
    """List all run_id folders that have JSONL failed-row logs."""
    base = Path(FAILED_LOG_DIR)
    if not base.is_dir():
        return []
    runs = []
    for d in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        files = [f.stem for f in d.glob("*.jsonl")]
        if files:
            runs.append({"run_id": d.name, "tables": sorted(files)})
    return runs


@app.post("/api/failed-logs/load-to-db")
def load_failed_logs_to_db(run_id: str, table: str = ""):
    """Load JSONL failed-row logs into <table>_failed_rows DB tables."""
    run_dir = Path(FAILED_LOG_DIR) / run_id
    if not run_dir.is_dir():
        raise HTTPException(404, f"Run folder not found: {run_id}")

    # Import the load_file helper from the project root
    project_root = Path(PIPELINE_DIR)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from load_failed_logs import load_file, _flatten

    files = sorted(run_dir.glob("*.jsonl"))
    if table:
        files = [f for f in files if f.stem == table]
    if not files:
        raise HTTPException(404, "No matching JSONL files found")

    loaded = {}
    for path in files:
        try:
            count = load_file(engine, SCHEMA, str(path))
            loaded[path.stem] = count
        except Exception as exc:
            logger.exception("Failed to load %s", path)
            loaded[path.stem] = f"error: {exc}"
    return {"loaded": loaded}
