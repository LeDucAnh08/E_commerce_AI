param(
    [string]$EnvFile = ".env",
    [string]$MaintenanceDb = "postgres"
)

$ErrorActionPreference = "Stop"

function Read-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Env file not found: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        $values[$key] = $value
    }

    return $values
}

function Require-Value {
    param(
        [hashtable]$Values,
        [string]$Key
    )

    if (-not $Values.ContainsKey($Key) -or [string]::IsNullOrWhiteSpace($Values[$Key])) {
        throw "Missing required env variable: $Key"
    }

    return $Values[$Key]
}

function Quote-PostgresIdentifier {
    param([string]$Identifier)
    return '"' + ($Identifier -replace '"', '""') + '"'
}

function Quote-PostgresLiteral {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

$envValues = Read-DotEnv -Path $EnvFile

$databaseName = Require-Value -Values $envValues -Key "PRODUCT_DB_NAME"
$databaseOwner = Require-Value -Values $envValues -Key "PRODUCT_DB_USER"
$databaseOwnerPassword = Require-Value -Values $envValues -Key "PRODUCT_DB_PASSWORD"
$hostName = if ($envValues["PRODUCT_DB_HOST"]) { $envValues["PRODUCT_DB_HOST"] } else { "127.0.0.1" }
$port = if ($envValues["PRODUCT_DB_PORT"]) { $envValues["PRODUCT_DB_PORT"] } else { "5432" }

$adminUser = if ($envValues["PRODUCT_DB_ADMIN_USER"]) { $envValues["PRODUCT_DB_ADMIN_USER"] } else { $databaseOwner }
$adminPassword = if ($envValues["PRODUCT_DB_ADMIN_PASSWORD"]) { $envValues["PRODUCT_DB_ADMIN_PASSWORD"] } else { $envValues["PRODUCT_DB_PASSWORD"] }
$adminHost = if ($envValues["PRODUCT_DB_ADMIN_HOST"]) { $envValues["PRODUCT_DB_ADMIN_HOST"] } elseif ($hostName -eq "host.docker.internal") { "127.0.0.1" } else { $hostName }
$adminPort = if ($envValues["PRODUCT_DB_ADMIN_PORT"]) { $envValues["PRODUCT_DB_ADMIN_PORT"] } else { $port }

if ([string]::IsNullOrWhiteSpace($adminUser)) {
    throw "Missing admin user. Set PRODUCT_DB_ADMIN_USER or PRODUCT_DB_USER in $EnvFile"
}

if ([string]::IsNullOrWhiteSpace($adminPassword)) {
    throw "Missing admin password. Set PRODUCT_DB_ADMIN_PASSWORD or PRODUCT_DB_PASSWORD in $EnvFile"
}

$psql = Get-Command psql -ErrorAction SilentlyContinue
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $psql -and -not $docker) {
    throw "Neither psql nor docker was found. Install PostgreSQL client tools or Docker."
}

$quotedDatabase = Quote-PostgresIdentifier -Identifier $databaseName
$quotedOwner = Quote-PostgresIdentifier -Identifier $databaseOwner
$databaseLiteral = Quote-PostgresLiteral -Value $databaseName
$ownerLiteral = Quote-PostgresLiteral -Value $databaseOwner
$ownerPasswordLiteral = Quote-PostgresLiteral -Value $databaseOwnerPassword

$sql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $ownerLiteral) THEN
        CREATE ROLE $quotedOwner LOGIN PASSWORD $ownerPasswordLiteral;
    END IF;
END
`$`$;

SELECT 'CREATE DATABASE $quotedDatabase OWNER $quotedOwner ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = $databaseLiteral)\gexec

GRANT ALL PRIVILEGES ON DATABASE $quotedDatabase TO $quotedOwner;
"@

$previousPassword = $env:PGPASSWORD
$env:PGPASSWORD = $adminPassword

try {
    Write-Host "Creating PostgreSQL database '$databaseName' on ${adminHost}:${adminPort} if needed..."

    if ($psql) {
        $sql | & $psql.Source `
            --host $adminHost `
            --port $adminPort `
            --username $adminUser `
            --dbname $MaintenanceDb `
            --no-password `
            --set ON_ERROR_STOP=1
        if ($LASTEXITCODE -ne 0) {
            throw "psql failed with exit code $LASTEXITCODE"
        }
    }
    else {
        $dockerHost = if ($adminHost -in @("127.0.0.1", "localhost")) { "host.docker.internal" } else { $adminHost }
        Write-Host "psql was not found locally. Using Docker image postgres:16-alpine as the PostgreSQL client..."
        $sql | & $docker.Source run --rm -i `
            -e "PGPASSWORD=$adminPassword" `
            postgres:16-alpine `
            psql `
            --host $dockerHost `
            --port $adminPort `
            --username $adminUser `
            --dbname $MaintenanceDb `
            --no-password `
            --set ON_ERROR_STOP=1
        if ($LASTEXITCODE -ne 0) {
            throw "Dockerized psql failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host "Done. Database '$databaseName' is ready for product_service."
}
finally {
    $env:PGPASSWORD = $previousPassword
}
