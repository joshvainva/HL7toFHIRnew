# Reset PostgreSQL postgres user password to Joshua@26489
# Run this PowerShell script as Administrator.

$serviceName = 'postgresql-x64-18'
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$pgData = 'C:\Program Files\PostgreSQL\18\data'
$password = 'Joshua@26489'

if (-not (Test-Path "$pgBin\postgres.exe")) {
    Write-Error "Postgres binary not found at $pgBin\postgres.exe"
    exit 1
}

Write-Host "Stopping PostgreSQL service '$serviceName'..."
Stop-Service -Name $serviceName -Force -ErrorAction Stop

Write-Host "Updating postgres password in single-user mode..."
$sql = "ALTER USER postgres WITH PASSWORD '$password';"
$escapedSql = $sql.Replace('"', '""')
$cmd = "echo $escapedSql | `"$pgBin\postgres.exe`" --single -D `"$pgData`" postgres"
Write-Host "Running: $cmd"
Invoke-Expression $cmd

Write-Host "Starting PostgreSQL service '$serviceName'..."
Start-Service -Name $serviceName -ErrorAction Stop

Write-Host "PostgreSQL password reset complete."
Write-Host "Ensure .env uses: DATABASE_URL=postgresql://postgres:Joshva%4026489@127.0.0.1:5432/innova_fhir"