# Power BI Desktop Bridge client (JSON-RPC over \\.\pipe\pbi-desktop-bridge-<PID>).
# Usage:
#   pbi-bridge.ps1 state
#   pbi-bridge.ps1 manifest
#   pbi-bridge.ps1 reload
#   pbi-bridge.ps1 screenshot -PageId <page name from page.json> -Out <file.png> [-Scale 1..3] [-Region x,y,w,h]
#   (-Region uses report.snapshot.capture/v2 in PBIR page units, e.g. 0,0,1920,1080 for a page-only image)
param(
    [Parameter(Mandatory)] [ValidateSet('manifest', 'state', 'reload', 'screenshot')] [string]$Action,
    [string]$PageId,
    [string]$Out,
    [ValidateRange(1, 3)] [int]$Scale = 1,
    [string]$Region,  # "x,y,w,h" (a string: -File passes comma lists as one argument)
    [int]$ProcessId
)
$ErrorActionPreference = 'Stop'

if (-not $ProcessId) {
    $ids = [IO.Directory]::GetFiles('\\.\pipe\') |
        ForEach-Object { if ($_ -match 'pbi-desktop-bridge-(\d+)$') { [int]$matches[1] } }
    if (-not $ids) { throw 'No Desktop Bridge pipe found. Is Power BI Desktop open with the bridge preview enabled?' }
    if (@($ids).Count -gt 1) { throw "Multiple Desktop instances ($($ids -join ', ')); pass -ProcessId." }
    $ProcessId = @($ids)[0]
}

# Message framing, as in the JSON-RPC base protocol: ASCII header lines, a blank line, then a UTF-8 body of exactly
# the byte count the Content-Length header names.
$EndOfHeaders = 0x0D0A0D0A  # CR LF CR LF, as the last four bytes read

function Read-Bytes($stream, [int]$count) {
    $data = New-Object byte[] $count
    $got = 0
    while ($got -lt $count) {
        $n = $stream.Read($data, $got, $count - $got)
        if ($n -le 0) { throw 'pipe closed' }
        $got += $n
    }
    , $data
}

function Receive-Message($stream) {
    $head = New-Object IO.MemoryStream
    [long]$last4 = 0
    do {
        $b = $stream.ReadByte()
        if ($b -lt 0) { throw 'pipe closed' }
        $head.WriteByte([byte]$b)
        $last4 = ($last4 * 256 + $b) % 4294967296
    } until ($last4 -eq $EndOfHeaders)
    $size = -1
    foreach ($line in [Text.Encoding]::ASCII.GetString($head.ToArray()) -split "`r`n") {
        $name, $value = $line -split ':', 2
        if ($null -ne $value -and $name.Trim() -eq 'Content-Length') { $size = [int]$value.Trim() }  # -eq ignores case
    }
    if ($size -lt 0) { throw 'bridge reply has no Content-Length header' }
    [Text.Encoding]::UTF8.GetString((Read-Bytes $stream $size)) | ConvertFrom-Json
}

function Send-Message($stream, [string]$json) {
    $body = [Text.Encoding]::UTF8.GetBytes($json)
    $frame = New-Object IO.MemoryStream
    $head = [Text.Encoding]::ASCII.GetBytes([string]::Format("Content-Length: {0}`r`n`r`n", $body.Length))
    $frame.Write($head, 0, $head.Length)
    $frame.Write($body, 0, $body.Length)
    $stream.Write($frame.ToArray(), 0, [int]$frame.Length)
    $stream.Flush()
}

function Invoke-Bridge($pipe, [int]$id, [string]$method, $params) {
    # Bridge methods take { client, args }; operation arguments go inside args.
    $wrapped = @{ client = 'pbip-polish'; args = $params }
    Send-Message $pipe (@{ jsonrpc = '2.0'; id = $id; method = $method; params = $wrapped } | ConvertTo-Json -Compress -Depth 10)
    $resp = Receive-Message $pipe
    if ($resp.error) { throw "$method failed: $($resp.error | ConvertTo-Json -Compress -Depth 5)" }
    $resp.result
}

$pipe = New-Object IO.Pipes.NamedPipeClientStream('.', "pbi-desktop-bridge-$ProcessId", [IO.Pipes.PipeDirection]::InOut)
try {
    $pipe.Connect(5000)
    switch ($Action) {
        'manifest' { Invoke-Bridge $pipe 1 'bridge.manifest' @{} | ConvertTo-Json -Depth 20 }
        'state' { Invoke-Bridge $pipe 1 'application.state.get/v1' @{} | ConvertTo-Json -Depth 5 }
        # reloadModelDefinition defaults to true on the bridge; keep the model untouched.
        'reload' { Invoke-Bridge $pipe 1 'file.reload/v1' @{ reloadModelDefinition = $false } | ConvertTo-Json }
        'screenshot' {
            if (-not $PageId -or -not $Out) { throw 'screenshot needs -PageId and -Out' }
            if ($Region) {
                $v = $Region.Split(',') | ForEach-Object { [double]$_.Trim() }
                $r = @{ x = $v[0]; y = $v[1]; width = $v[2]; height = $v[3] }
                $shot = Invoke-Bridge $pipe 1 'report.snapshot.capture/v2' @{ pageId = $PageId; scale = $Scale; region = $r }
            } else {
                $shot = Invoke-Bridge $pipe 1 'report.snapshot.capture/v1' @{ pageId = $PageId; scale = $Scale }
            }
            $path = [IO.Path]::GetFullPath($Out)
            [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($shot.payload))
            "Saved '$($shot.pageDisplayName)' ($($shot.pageId)) to $path"
        }
    }
}
finally { $pipe.Dispose() }
