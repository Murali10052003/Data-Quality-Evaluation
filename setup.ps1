# ── DQ Eval  ·  One-time setup script ────────────────────────────────────────
# Run this after cloning the repo. It will:
#   1. Collect your PostgreSQL connection details
#   2. Create the .env file
#   3. Install Python dependencies (root + backend)
#   4. Install frontend Node.js dependencies
#   5. Create dq_control and dq_results tables in your database
#
# Prerequisites: Python 3.10+, Node.js 18+, psql (PostgreSQL client)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   DQ Eval — Project Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# ── Step 1: Collect database connection details ──────────────────────────────
Write-Host "[1/5] Database connection details`n" -ForegroundColor Yellow

$dbHost     = Read-Host "  PostgreSQL host     (default: localhost)"
$dbPort     = Read-Host "  PostgreSQL port     (default: 5432)"
$dbName     = Read-Host "  Database name       (default: postgres)"
$dbUser     = Read-Host "  Database user       (default: postgres)"
$dbSchema   = Read-Host "  Schema              (default: public)"

if ([string]::IsNullOrWhiteSpace($dbHost))   { $dbHost   = "localhost" }
if ([string]::IsNullOrWhiteSpace($dbPort))   { $dbPort   = "5432" }
if ([string]::IsNullOrWhiteSpace($dbName))   { $dbName   = "postgres" }
if ([string]::IsNullOrWhiteSpace($dbUser))   { $dbUser   = "postgres" }
if ([string]::IsNullOrWhiteSpace($dbSchema)) { $dbSchema = "public" }

Write-Host ""
$authChoice = Read-Host "  Auth method — (1) Password  or  (2) Azure Entra token?  [1/2]"

if ($authChoice -eq "2") {
    Write-Host "  Fetching Azure Entra token..." -ForegroundColor Cyan
    $dbPassword = $(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Could not get Azure token. Run 'az login' first." -ForegroundColor Red
        Write-Host "  $dbPassword" -ForegroundColor Red
        pause; exit 1
    }
    Write-Host "  Token obtained." -ForegroundColor Green
} else {
    $securePass = Read-Host "  Database password" -AsSecureString
    $dbPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    )
}

# Determine SSL mode based on host
if ($dbHost -match "\.database\.azure\.com$") {
    $sslMode = "require"
} else {
    $sslChoice = Read-Host "  SSL mode — (1) require  (2) prefer  (3) disable  [default: require]"
    switch ($sslChoice) {
        "2" { $sslMode = "prefer" }
        "3" { $sslMode = "disable" }
        default { $sslMode = "require" }
    }
}

# ── Step 2: Create .env file ─────────────────────────────────────────────────
Write-Host "`n[2/5] Creating .env file..." -ForegroundColor Yellow

$envContent = @"
# ── PostgreSQL connection ─────────────────────────────────────────────────────
DQ_DB_HOST=$dbHost
DQ_DB_PORT=$dbPort
DQ_DB_NAME=$dbName
DQ_DB_USER=$dbUser
DQ_DB_PASSWORD=$dbPassword
DQ_DB_SSLMODE=$sslMode

# ── Schema and metadata tables ────────────────────────────────────────────────
DQ_DB_SCHEMA=$dbSchema
DQ_CONTROL_TABLE=dq_control
DQ_RESULTS_TABLE=dq_results

# ── Pipeline behaviour ────────────────────────────────────────────────────────
DQ_LOG_LEVEL=INFO
"@

Set-Content -Path ".env" -Value $envContent -Encoding UTF8
Write-Host "  .env created." -ForegroundColor Green

# ── Step 3: Install Python dependencies ──────────────────────────────────────
Write-Host "`n[3/5] Installing Python dependencies..." -ForegroundColor Yellow

# Verify Python version — psycopg2-binary needs 3.10–3.12
$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python version: $pyVer" -ForegroundColor White
$minor = [int]($pyVer.Split('.')[1])
if ($minor -gt 12) {
    Write-Host "  WARNING: psycopg2-binary may not have prebuilt wheels for Python $pyVer." -ForegroundColor Yellow
    Write-Host "  If install fails, use Python 3.10, 3.11, or 3.12." -ForegroundColor Yellow
}

pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: pip install (root) failed." -ForegroundColor Red
    Write-Host "  If psycopg2-binary failed, install Python 3.10–3.12 and retry." -ForegroundColor Yellow
    pause; exit 1
}

pip install -r backend/requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "  ERROR: pip install (backend) failed." -ForegroundColor Red; pause; exit 1 }

Write-Host "  Python dependencies installed." -ForegroundColor Green

# ── Step 4: Install frontend dependencies ────────────────────────────────────
Write-Host "`n[4/5] Installing frontend dependencies..." -ForegroundColor Yellow

Push-Location frontend
npm install --silent
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Host "  ERROR: npm install failed." -ForegroundColor Red; pause; exit 1 }
Pop-Location

Write-Host "  Frontend dependencies installed." -ForegroundColor Green

# ── Step 5: Create database tables ───────────────────────────────────────────
Write-Host "`n[5/5] Creating database tables (dq_control, dq_results)..." -ForegroundColor Yellow

$sslArg = if ($sslMode -eq "disable") { "" } else { "sslmode=$sslMode" }
$env:PGPASSWORD = $dbPassword

$createSQL = @"
CREATE TABLE IF NOT EXISTS dq_control (
    control_id  SERIAL PRIMARY KEY,
    schema_name VARCHAR(100) NOT NULL,
    table_name  VARCHAR(100) NOT NULL,
    dqmethod    VARCHAR(100) NOT NULL,
    config      JSONB NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dq_results (
    run_id        TEXT        NOT NULL,
    schema_name   TEXT        NOT NULL,
    table_name    TEXT        NOT NULL,
    dqmethod      TEXT        NOT NULL,
    col           TEXT        NOT NULL DEFAULT 'N/A',
    status        TEXT,
    run_timestamp TIMESTAMPTZ,
    dqevalcount   BIGINT      DEFAULT 0,
    PRIMARY KEY (run_id, schema_name, table_name, dqmethod, col)
);

CREATE INDEX IF NOT EXISTS idx_dq_results_run_id       ON dq_results (run_id);
CREATE INDEX IF NOT EXISTS idx_dq_results_timestamp    ON dq_results (run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dq_results_status_ts    ON dq_results (status, run_timestamp);
CREATE INDEX IF NOT EXISTS idx_dq_results_ts_status    ON dq_results (run_timestamp, status);
CREATE INDEX IF NOT EXISTS idx_dq_results_table_method ON dq_results (table_name, dqmethod, status);
"@

$psqlArgs = @("-h", $dbHost, "-p", $dbPort, "-U", $dbUser, "-d", $dbName, "-c", $createSQL)
if ($sslArg) { $psqlArgs += @("--set=sslmode=$sslMode") }

$result = psql @psqlArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Could not create tables. Check your connection details." -ForegroundColor Red
    Write-Host "  $result" -ForegroundColor Red
    Write-Host "`n  You can create the tables manually using sql_queries/dq_control_query.sql" -ForegroundColor Yellow
    Write-Host "  and sql_queries/dq_results_query.sql" -ForegroundColor Yellow
} else {
    Write-Host "  Tables created successfully." -ForegroundColor Green
}

Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n  Start the app with:" -ForegroundColor White
Write-Host "    Terminal 1:  .\start_backend.ps1" -ForegroundColor White
Write-Host "    Terminal 2:  .\start_frontend.ps1" -ForegroundColor White
Write-Host "    Then open:   http://localhost:3030`n" -ForegroundColor White
