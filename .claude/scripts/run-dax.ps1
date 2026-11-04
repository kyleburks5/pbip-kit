# Read-only: run the DAX query in a file against the open Desktop model (ADOMD client shipped with Desktop).
# Usage: run-dax.ps1 -File <query.dax> -Port <port>   (port: wireframe_data.py --port auto finds it, or the
# modeling MCP ListLocalInstances; no default: a remembered port is a closed Desktop's)
param([Parameter(Mandatory)][string]$File, [Parameter(Mandatory)][int]$Port)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8  # callers decode UTF-8
$sep = ' ' + [char]0xA6 + ' '  # the file is read as ANSI by PowerShell 5.1, so no literal non-ASCII here
$exe = (Get-Process PBIDesktop | Select-Object -First 1).Path
Add-Type -Path (Join-Path (Split-Path $exe) 'Microsoft.PowerBI.AdomdClient.dll')
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$Port"
$conn.Open()
try {
    $cmd = $conn.CreateCommand(); $cmd.CommandText = [IO.File]::ReadAllText($File); $cmd.CommandTimeout = 300
    $r = $cmd.ExecuteReader()
    while ($r.Read()) {
        $vals = for ($i = 0; $i -lt $r.FieldCount; $i++) { $v = $r.GetValue($i); if ($null -eq $v) { '(blank)' } else { "$v" } }
        Write-Output ($vals -join $sep)
        Write-Output '----'
    }
    $r.Close()
} catch { Write-Output "ERROR: $($_.Exception.Message)" } finally { $conn.Close() }
