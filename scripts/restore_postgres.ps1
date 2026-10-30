param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"
$databaseUrl = $env:DATABASE_URL
if ([string]::IsNullOrWhiteSpace($databaseUrl)) {
    throw "Set DATABASE_URL before restoring a PostgreSQL backup."
}
if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
    throw "Backup file was not found: $BackupFile"
}
if (-not $Confirm) {
    throw "Restore replaces database objects. Re-run with -Confirm after taking a current backup."
}

& pg_restore --clean --if-exists --no-owner --dbname=$databaseUrl $BackupFile
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed with exit code $LASTEXITCODE."
}

Write-Output "Restore completed from: $BackupFile"
