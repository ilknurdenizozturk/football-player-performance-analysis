$proc = Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $proc) {
    Write-Error "Power BI Desktop is not open or msmdsrv process was not found."
    exit
}
$portLine = netstat -ano | Select-String "LISTENING" | Select-String "\s$($proc.Id)$" | Select-Object -First 1
if ($null -eq $portLine) {
    Write-Error "Could not detect msmdsrv port (PID $($proc.Id))."
    exit
}
$Port = [int]($portLine.Line.Trim() -split '\s+')[1].Split(':')[-1]
Write-Output "msmdsrv PID: $($proc.Id) -> Port: $Port"

$bin = 'C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_2.155.756.0_x64__8wekyb3d8bbwe\bin'
if (-not (Test-Path $bin)) {
    # Fallback to general location if Windows Store app path differs
    $bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
}
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Core.dll')
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Tabular.dll')

$connStr = "Provider=MSOLAP;Data Source=localhost:$Port"
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect($connStr)

$db = $server.Databases[0]
Write-Output "Connected to Database: $($db.Name)"
Write-Output "Checking tables for errors..."

foreach ($table in $db.Model.Tables) {
    $hasError = $false
    $errorMsg = ""
    
    # Check table status / errors
    if ($table.ErrorMessage) {
        $hasError = $true
        $errorMsg = $table.ErrorMessage
    }
    
    foreach ($partition in $table.Partitions) {
        if ($partition.ErrorMessage) {
            $hasError = $true
            $errorMsg += " [Partition Error: $($partition.ErrorMessage)]"
        }
    }
    
    # Also check if table has no data (refreshed status)
    $rowCount = 0
    # We can try to see if it is refreshed by looking at its partitions
    $lastRefreshed = ""
    foreach ($partition in $table.Partitions) {
        if ($partition.RefreshedTime) {
            $lastRefreshed = $partition.RefreshedTime.ToString()
        }
    }

    if ($hasError) {
        Write-Output "❌ Table '$($table.Name)': $errorMsg"
    } else {
        if ([string]::IsNullOrEmpty($lastRefreshed)) {
            Write-Output "⚠️ Table '$($table.Name)': Not refreshed / no data loaded."
        } else {
            Write-Output "✅ Table '$($table.Name)': Refreshed at $lastRefreshed."
        }
    }
}

$server.Disconnect()
