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

$bin = 'C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_2.155.756.0_x64__8wekyb3d8bbwe\bin'
if (-not (Test-Path $bin)) {
    $bin = "C:\Program Files\Microsoft Power BI Desktop\bin"
}

# Load ADOMD client DLL
$adomdDll = Join-Path $bin 'Microsoft.AnalysisServices.AdomdClient.dll'
if (-not (Test-Path $adomdDll)) {
    Write-Error "AdomdClient.dll not found."
    exit
}
Add-Type -Path $adomdDll

$connStr = "Provider=MSOLAP;Data Source=localhost:$Port"
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection($connStr)

try {
    $conn.Open()
    Write-Output "Connected successfully to Analysis Services!"
} catch {
    Write-Error "Failed to connect: $_"
    exit
}

# Get database name
$dbName = $conn.Database
Write-Output "Active Database: $dbName"

# Load Tabular to get the list of measures
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Core.dll')
Add-Type -Path (Join-Path $bin 'Microsoft.AnalysisServices.Server.Tabular.dll')
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("localhost:$Port")
$db = $server.Databases[$dbName]

Write-Output "`nTesting all measures..."
foreach ($table in $db.Model.Tables) {
    if ($table.Measures.Count -eq 0) { continue }
    Write-Output "`n--- Table: $($table.Name) ---"
    
    foreach ($measure in $table.Measures) {
        $measureName = $measure.Name
        # Run a simple DAX query to evaluate this measure
        $daxQuery = "EVALUATE ROW(""Result"", [$measureName])"
        
        $cmd = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdCommand($daxQuery, $conn)
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $reader = $cmd.ExecuteReader()
            $stopwatch.Stop()
            if ($reader.Read()) {
                $val = $reader.GetValue(0)
                Write-Output "✅ Measure '$measureName': Success (Value: $val) in $($stopwatch.ElapsedMilliseconds)ms"
            }
            $reader.Close()
        } catch {
            $stopwatch.Stop()
            Write-Output "❌ Measure '$measureName': FAILED!"
            Write-Output "   Error: $($_.Exception.Message)"
        }
    }
}

$conn.Close()
$server.Disconnect()
