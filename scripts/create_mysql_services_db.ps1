param(
    [string]$EnvFile = ".env"
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

function Quote-MySqlIdentifier {
    param([string]$Identifier)
    return '`' + ($Identifier -replace '`', '``') + '`'
}

function Quote-MySqlLiteral {
    param([string]$Value)
    return "'" + ($Value -replace "'", "''") + "'"
}

$envValues = Read-DotEnv -Path $EnvFile

$databaseName = Require-Value -Values $envValues -Key "MYSQL_DB_NAME"
$databaseUser = Require-Value -Values $envValues -Key "MYSQL_DB_USER"
$databasePassword = Require-Value -Values $envValues -Key "MYSQL_DB_PASSWORD"
$hostName = if ($envValues["MYSQL_DB_HOST"]) { $envValues["MYSQL_DB_HOST"] } else { "127.0.0.1" }
$port = if ($envValues["MYSQL_DB_PORT"]) { $envValues["MYSQL_DB_PORT"] } else { "3306" }

$adminUser = if ($envValues["MYSQL_DB_ADMIN_USER"]) { $envValues["MYSQL_DB_ADMIN_USER"] } else { $databaseUser }
$adminPassword = if ($envValues["MYSQL_DB_ADMIN_PASSWORD"]) { $envValues["MYSQL_DB_ADMIN_PASSWORD"] } else { $databasePassword }
$adminHost = if ($envValues["MYSQL_DB_ADMIN_HOST"]) { $envValues["MYSQL_DB_ADMIN_HOST"] } elseif ($hostName -eq "host.docker.internal") { "127.0.0.1" } else { $hostName }
$adminPort = if ($envValues["MYSQL_DB_ADMIN_PORT"]) { $envValues["MYSQL_DB_ADMIN_PORT"] } else { $port }

if ([string]::IsNullOrWhiteSpace($adminUser)) {
    throw "Missing admin user. Set MYSQL_DB_ADMIN_USER or MYSQL_DB_USER in $EnvFile"
}

if ([string]::IsNullOrWhiteSpace($adminPassword)) {
    throw "Missing admin password. Set MYSQL_DB_ADMIN_PASSWORD or MYSQL_DB_PASSWORD in $EnvFile"
}

$mysql = Get-Command mysql -ErrorAction SilentlyContinue
if (-not $mysql) {
    $mysqlCandidates = @(
        "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Workbench 8.0 CE\mysql.exe",
        "C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin\mysql.exe",
        "C:\Program Files (x86)\MySQL\MySQL Workbench 8.0 CE\mysql.exe"
    )
    foreach ($candidate in $mysqlCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            $mysql = @{ Source = $candidate }
            break
        }
    }
}
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $mysql -and -not $docker) {
    throw "Neither mysql nor docker was found. Install MySQL client tools or Docker."
}

$quotedDatabase = Quote-MySqlIdentifier -Identifier $databaseName
$userLiteral = Quote-MySqlLiteral -Value $databaseUser
$passwordLiteral = Quote-MySqlLiteral -Value $databasePassword

$sql = @"
CREATE DATABASE IF NOT EXISTS $quotedDatabase
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS $userLiteral@'%' IDENTIFIED BY $passwordLiteral;
ALTER USER $userLiteral@'%' IDENTIFIED BY $passwordLiteral;
GRANT ALL PRIVILEGES ON $quotedDatabase.* TO $userLiteral@'%';
FLUSH PRIVILEGES;
"@

try {
    Write-Host "Creating MySQL database '$databaseName' on ${adminHost}:${adminPort} if needed..."

    if ($mysql) {
        $env:MYSQL_PWD = $adminPassword
        $sql | & $mysql.Source `
            --host=$adminHost `
            --port=$adminPort `
            --user=$adminUser `
            --protocol=TCP
        if ($LASTEXITCODE -ne 0) {
            throw "mysql failed with exit code $LASTEXITCODE"
        }
    }
    else {
        $dockerHost = if ($adminHost -in @("127.0.0.1", "localhost")) { "host.docker.internal" } else { $adminHost }
        Write-Host "mysql was not found locally. Using Docker image mysql:8.4 as the MySQL client..."
        $sql | & $docker.Source run --rm -i `
            mysql:8.4 `
            mysql `
            --host=$dockerHost `
            --port=$adminPort `
            --user=$adminUser `
            "--password=$adminPassword" `
            --protocol=TCP
        if ($LASTEXITCODE -ne 0) {
            throw "Dockerized mysql failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host "Done. Database '$databaseName' is ready for non-product services."
}
finally {
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}
