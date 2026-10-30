param(
    [string]$OutputDirectory = ".\backups"
)

$ErrorActionPreference = "Stop"
$databaseUrl = $env:DATABASE_URL
if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
    throw "Set DATABASE_URL before creating a PostgreSQL backup."
}

$directory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputFile = Join-Path $directory "pharmacy-$timestamp.dump"

& pg_dump $databaseUrl --format=custom --file=$outputFile
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed with exit code $LASTEXITCODE."
}

Write-Output "Backup created: $outputFile"
