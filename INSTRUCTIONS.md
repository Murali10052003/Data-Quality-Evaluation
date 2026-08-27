# DQ Eval — Setup Instructions

Step-by-step guide to connect your own PostgreSQL database and run DQ Eval locally.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| PostgreSQL | 13+ | `psql --version` |
| Git | any | `git --version` |

> **Azure users only:** If your PostgreSQL is Azure Database for PostgreSQL with Entra (AAD) authentication, you also need the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed and logged in (`az login`).

---

## 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Dqeval_notebooks
```

---

## 2. Configure Database Connection

### 2.1 Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your PostgreSQL connection details:

```env
# ── PostgreSQL connection ────────────────────────────────
DQ_DB_HOST=localhost          # your Postgres host (e.g. localhost, 10.0.0.5, mydb.postgres.database.azure.com)
DQ_DB_PORT=5432               # default Postgres port
DQ_DB_NAME=mydb               # your database name
DQ_DB_USER=postgres           # your database username
DQ_DB_PASSWORD=your_password  # your database password (see 2.2 for Azure AAD token)

# ── Schema and metadata tables ───────────────────────────
DQ_DB_SCHEMA=public           # schema where your business tables live
DQ_CONTROL_TABLE=dq_control   # leave as-is unless you renamed it
DQ_RESULTS_TABLE=dq_results   # leave as-is unless you renamed it

# ── Pipeline behaviour ───────────────────────────────────
DQ_LOG_LEVEL=INFO             # DEBUG | INFO | WARNING | ERROR
```

### 2.2 Azure Entra (AAD) token authentication (Azure users only)

If your PostgreSQL uses Azure AD authentication instead of a static password, fetch a token and set it as the password:

**PowerShell:**
```powershell
az login
$token = az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken --output tsv
# Update .env
$content = Get-Content -Path .env
$updated = $content -replace '^DQ_DB_PASSWORD=.*', "DQ_DB_PASSWORD=$token"
Set-Content -Path .env -Value $updated
```

**Bash/Zsh:**
```bash
az login
TOKEN=$(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken --output tsv)
sed -i "s/^DQ_DB_PASSWORD=.*/DQ_DB_PASSWORD=$TOKEN/" .env
```

> **Note:** Azure tokens expire in ~75 minutes. The backend auto-refreshes them at runtime via `azure-identity`, but you may need to re-run `az login` if your session expires.

### 2.3 SSL mode

The pipeline defaults to `sslmode=require`. If your local PostgreSQL does not use SSL, you can either:
- Configure SSL on your Postgres server (recommended), or
- For local-only development, temporarily modify the connection URL in `dq_pipeline/config.py` (line ~58) to change `?sslmode=require` to `?sslmode=prefer` or `?sslmode=disable`.

---

## 3. Set Up the Database Tables

Connect to your PostgreSQL database using `psql`, pgAdmin, Azure Data Studio, or any SQL client and run the following DDL scripts **in order**.

### 3.1 Create the metadata tables

These two tables are required — DQ Eval stores rules and results here:

```sql
-- From: sql_queries/dq_control_query.sql (CREATE TABLE part only)

CREATE TABLE dq_control (
    control_id SERIAL PRIMARY KEY,
    schema_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    dqmethod VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

```sql
-- From: sql_queries/dq_results_query.sql

CREATE TABLE dq_results (
    run_id         TEXT         NOT NULL,
    schema_name    TEXT         NOT NULL,
    table_name     TEXT         NOT NULL,
    dqmethod       TEXT         NOT NULL,
    col            TEXT         NOT NULL DEFAULT 'N/A',
    status         TEXT,
    run_timestamp  TIMESTAMPTZ,
    dqevalcount    BIGINT       DEFAULT 0,
    PRIMARY KEY (run_id, schema_name, table_name, dqmethod, col)
);
```

---

## 4. Install Dependencies

### 4.1 Python (backend + pipeline)

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

> **Optional:** Install the `dqeval` library from the included wheel for standalone use:
> ```bash
> pip install dqeval-0.1.0-py3-none-any.whl
> ```

### 4.2 Node.js (frontend)

```bash
cd frontend
npm install
cd ..
```

---

## 5. Run the Application

You need **two terminals** — one for the backend, one for the frontend.

### Option A: PowerShell scripts (Windows)

**Terminal 1 — Backend:**
```powershell
.\start_backend.ps1
```

**Terminal 2 — Frontend:**
```powershell
.\start_frontend.ps1
```

### Option B: Manual commands (any OS)

**Terminal 1 — Backend:**
```bash
cd backend
python -m uvicorn main_api:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### Open the UI

Navigate to **http://localhost:3030** in your browser. The Vite dev server automatically proxies all `/api/*` calls to the FastAPI backend on port 8000.

---

## 6. Run the Pipeline (CLI, without the UI)

You can also run data quality checks directly from the command line:

```bash
python main.py                                  # all active rules, 500K rows per chunk
```

Filter to a specific schema/table:

```bash
# PowerShell
$env:DQ_FILTER_SCHEMA="public"
$env:DQ_FILTER_TABLE="employee_lowdata"
python main.py

# Bash
DQ_FILTER_SCHEMA=public DQ_FILTER_TABLE=employee_lowdata python main.py
```

Adjust chunk size for large tables:

```bash
# PowerShell
$env:DQ_BATCH_SIZE=1000000; python main.py

# Bash
DQ_BATCH_SIZE=1000000 python main.py
```

---

## 7. Verify It Works

1. Open **http://localhost:3030/rules** — you should see any rules you inserted into `dq_control`.
2. Go to **http://localhost:3030/run** — select your schema and table, click **Run**.
3. Check **http://localhost:3030/results** — you should see pass/fail results.
4. View **http://localhost:3030/dashboard** — KPI cards and charts.

---

## Quick Reference: Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DQ_DB_HOST` | `localhost` | PostgreSQL hostname |
| `DQ_DB_PORT` | `5432` | PostgreSQL port |
| `DQ_DB_NAME` | `postgres` | Database name |
| `DQ_DB_USER` | `postgres` | Database username |
| `DQ_DB_PASSWORD` | (empty) | Database password or Azure AD token |
| `DQ_DB_SCHEMA` | `public` | Schema for business + metadata tables |
| `DQ_DB_SSLMODE` | `require` | SSL mode (backend only) |
| `DQ_CONTROL_TABLE` | `dq_control` | Rule catalog table name |
| `DQ_RESULTS_TABLE` | `dq_results` | Results table name |
| `DQ_FAILED_LOG_DIR` | `failed_logs` | Directory for failed-row JSONL logs |
| `DQ_BATCH_SIZE` | `500000` | Rows per chunk for large-table streaming |
| `DQ_FILTER_SCHEMA` | (all) | Restrict pipeline to this schema |
| `DQ_FILTER_TABLE` | (all) | Restrict pipeline to this table |
| `DQ_LOG_LEVEL` | `INFO` | Logging verbosity |
| `DQ_CORS_ORIGINS` | (empty) | Extra CORS origins for the backend (comma-separated) |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `psycopg2` install fails | Install `psycopg2-binary` instead: `pip install psycopg2-binary` |
| `FATAL: password authentication failed` | Double-check `DQ_DB_USER` and `DQ_DB_PASSWORD` in `.env` |
| `FATAL: no pg_hba.conf entry for host` | Add your IP to the PostgreSQL server's `pg_hba.conf` or Azure firewall rules |
| `SSL connection is required` | Set `sslmode=require` or configure SSL on your Postgres server |
| `sslmode=require` fails on local Postgres | Change sslmode to `prefer` or `disable` in `dq_pipeline/config.py` (line ~58) |
| Azure token expired | Re-run `az login` and restart the backend, or let the auto-refresh handle it |
| Frontend shows network errors | Make sure the backend is running on port 8000 before starting the frontend |
| `npm run dev` port conflict | Port 3030 is hardcoded in `frontend/vite.config.ts` — change it there if needed |
| Tables not showing in Rule Manager | Ensure your tables exist in the schema specified by `DQ_DB_SCHEMA` |
