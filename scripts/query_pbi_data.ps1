$proc = Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $proc) {
    Write-Error "Power BI Desktop is not open."
    exit
}
$portLine = netstat -ano | Select-String "LISTENING" | Select-String "\s$($proc.Id)$" | Select-Object -First 1
if ($null -eq $portLine) {
    Write-Error "Could not detect port."
    exit
}
$Port = [int]($portLine.Line.Trim() -split '\s+')[1].Split(':')[-1]
Write-Output "msmdsrv Port: $Port"

# Connect using OLE DB (built-in, no external DLL needed)
$connStr = "Provider=MSOLAP;Data Source=localhost:$Port"
$conn = New-Object System.Data.OleDb.OleDbConnection($connStr)

try {
    $conn.Open()
} catch {
    Write-Error "Failed to connect: $_"
    exit
}

# Get database name
$dbName = $conn.Database
Write-Output "Connected to Database: $dbName"

# Query row counts of key tables
$tables = @(
    "dim_players",
    "dim_clubs",
    "fct_transfers",
    "fct_transfer_market_value_analysis",
    "ml_player_market_value_current_predictions"
)

foreach ($tableName in $tables) {
    # Check if table exists in DMV first
    $checkQuery = "select [TABLE_NAME] from `$system.DBSCHEMA_TABLES where [TABLE_NAME] = '$tableName'"
    $checkCmd = New-Object System.Data.OleDb.OleDbCommand($checkQuery, $conn)
    $exists = $null -ne $checkCmd.ExecuteScalar()
    
    if (-not $exists) {
        Write-Output "Table '$tableName' does not exist in the active model."
        continue
    }

    $daxQuery = "EVALUATE ROW(""Count"", COUNTROWS('$tableName'))"
    $cmd = New-Object System.Data.OleDb.OleDbCommand($daxQuery, $conn)
    try {
        $count = $cmd.ExecuteScalar()
        Write-Output "Table '$tableName': $count rows"
    } catch {
        Write-Output "Table '$tableName': failed to query: $_"
    }
}

$conn.Close()
