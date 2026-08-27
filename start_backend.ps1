# ── DQ Eval UI  ·  Backend launcher ──────────────────────────────────────────
# Run this from any directory.  It will:
#   1. Move to the backend folder
#   2. Install / upgrade Python dependencies (fast if already installed)
#   3. Fetch a fresh Azure Entra token
#   4. Start uvicorn on port 8000

Set-Location "$PSScriptRoot\backend"

Write-Host "`n[1/3] Installing Python dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet

Write-Host "[2/3] Fetching Azure Entra token..." -ForegroundColor Cyan
$token = $(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv 2>&1)
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  ERROR: Could not get Azure token. Run 'az login' first." -ForegroundColor Red
    Write-Host "  $token" -ForegroundColor Red
    pause
    exit 1
}
$env:DQ_DB_PASSWORD = $token
Write-Host "  Token obtained (expires ~75 min)." -ForegroundColor Green

Write-Host "[3/3] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Cyan
python -m uvicorn main_api:app --reload --port 8000
