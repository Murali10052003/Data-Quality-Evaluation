# ── DQ Eval UI  ·  Frontend launcher ─────────────────────────────────────────
# Run this from any directory.  It will:
#   1. Move to the frontend folder
#   2. Run npm install if node_modules is missing or package.json changed
#   3. Start Vite dev server on http://localhost:3030

Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "`n[1/2] node_modules not found. Running npm install..." -ForegroundColor Cyan
    npm install
} else {
    Write-Host "`n[1/2] node_modules present. Skipping install." -ForegroundColor Green
}

Write-Host "[2/2] Starting Vite dev server on http://localhost:3030 ..." -ForegroundColor Cyan
npm run dev
