# setup_db.ps1 — Create the AquaSense PostgreSQL database
# Run this ONCE after installing PostgreSQL.

param(
    [string]$Password = "",
    [string]$Host     = "localhost",
    [string]$Port     = "5432",
    [string]$User     = "postgres",
    [string]$DbName   = "aquasense"
)

if (-not $Password) {
    $Password = Read-Host "Enter your PostgreSQL 'postgres' user password"
}

Write-Host "`nCreating database '$DbName'..." -ForegroundColor Cyan

$env:PGPASSWORD = $Password
$psql = "psql"

# Try to find psql in common locations
$candidates = @(
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe",
    "C:\Program Files\PostgreSQL\14\bin\psql.exe"
)
foreach ($c in $candidates) {
    if (Test-Path $c) { $psql = $c; break }
}

# Create database
& $psql -h $Host -p $Port -U $User -c "CREATE DATABASE $DbName;" postgres 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Database '$DbName' created!" -ForegroundColor Green
} else {
    Write-Host "   Database may already exist (that's fine)" -ForegroundColor Yellow
}

# Update .env
$envFile = Join-Path $PSScriptRoot "..\..\.env"
if (Test-Path $envFile) {
    $content = Get-Content $envFile -Raw
    $newUrl  = "DATABASE_URL=postgresql://${User}:${Password}@${Host}:${Port}/${DbName}"
    $content = $content -replace "DATABASE_URL=.*", $newUrl
    Set-Content $envFile $content
    Write-Host "   Updated DATABASE_URL in .env" -ForegroundColor Green
}

Write-Host "`nDone! Now restart the API server to apply the changes." -ForegroundColor Green
Write-Host "   DATABASE_URL=postgresql://${User}:***@${Host}:${Port}/${DbName}" -ForegroundColor White
