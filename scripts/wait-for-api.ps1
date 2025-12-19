param(
    [string]$url = "http://localhost:8000/health",
    [int]$timeout = 60
)

Write-Host "Waiting for $url"
$start = Get-Date
while ($true) {
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { Write-Host "OK"; exit 0 }
    } catch {
        # ignore and retry
    }
    if ((Get-Date) - $start).TotalSeconds -ge $timeout { Write-Host "Timeout after $timeout seconds"; exit 1 }
    Start-Sleep -Seconds 2
}
