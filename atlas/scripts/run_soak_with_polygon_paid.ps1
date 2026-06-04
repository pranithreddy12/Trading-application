<#
Helper: Run the short soak using a paid Polygon API key.

Usage (PowerShell):
$env:POLYGON_API_KEY = 'your_paid_key_here'
./atlas/scripts/run_soak_with_polygon_paid.ps1

The script sets `POLYGON_DELAYED=False` and disables the yfinance fallback.
#>

if (-not $env:POLYGON_API_KEY) {
    Write-Error "POLYGON_API_KEY is not set. Export your paid Polygon key as POLYGON_API_KEY and rerun."
    exit 1
}

# Ensure we request live Polygon data
$env:POLYGON_DELAYED = 'False'
# Disable yfinance fallback when using paid Polygon
$env:POLYGON_FALLBACK_YFINANCE = '0'

# Default soak length if not provided
if (-not $env:SOAK_SECONDS) {
    $env:SOAK_SECONDS = '3600'
}

Write-Host "Starting soak with paid Polygon key (SOAK_SECONDS=$($env:SOAK_SECONDS))..."
python atlas/scripts/run_short_soak.py
