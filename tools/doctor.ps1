# pbip-kit go/no-go check for a locked-down work laptop (read-only). Each line says PASS, WARN or FAIL:
#   PASS  ready as is
#   WARN  works with the fallback printed under it (the kit has one for every WARN)
#   FAIL  the kit can't run that step: the line under it says what to ask IT (docs/IT-REQUEST.md is the full request)
# Checks: Python, pip or an offline install, jsonschema (optional), pbik, the PowerShell execution policy, Node.js /
# npx and npm registry access (the modeling MCP and daxlib-mcp start through npx), Power BI Desktop against
# VERSIONS.md, compatibility level 1702 (DAX Lib), the Desktop Bridge, Deneb (custom visuals), Git, proxy, the kit
# folder and the Copilot files.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1 [-Offline]
#   -Offline  skip the network checks (pip index, npm registry)
# Exits 1 if anything FAILs (NO-GO). Changes nothing (temp files only, removed).
param([switch]$Offline)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$fails = 0; $warns = 0

function Report([string]$status, [string]$item, [string]$detail, [string]$next = '') {
    $color = @{ PASS = 'Green'; WARN = 'Yellow'; FAIL = 'Red' }[$status]
    Write-Host ("{0,-5} {1,-26} {2}" -f $status, $item, $detail) -ForegroundColor $color
    if ($status -eq 'WARN') { $script:warns++; if (-not $next) { $next = 'see docs/IT-REQUEST.md' }; Write-Host "      fallback: $next" }
    if ($status -eq 'FAIL') { $script:fails++; if (-not $next) { $next = 'see docs/IT-REQUEST.md' }; Write-Host "      ask IT: $next" }
}

function Run-WithTimeout([scriptblock]$block, [object[]]$argList, [int]$seconds = 45) {
    # npm and pip can hang behind a proxy: run in a job and give up after $seconds (returns $null on timeout)
    $job = Start-Job -ScriptBlock $block -ArgumentList $argList
    if (Wait-Job $job -Timeout $seconds) { $out = Receive-Job $job; Remove-Job $job -Force; return $out }
    Stop-Job $job; Remove-Job $job -Force; return $null
}

# ---------------------------------------------------------------- Python, pip, jsonschema, pbik
$py = Get-Command python -ErrorAction SilentlyContinue
$real = $null
if ($py -and $py.Source -match 'WindowsApps') {
    $real = (& python -c "import sys; print(sys.executable)" 2>$null)
    if (-not $real) {
        Report 'FAIL' 'Python' "python is the Microsoft Store stub ($($py.Source))" 'install Python 3.9+ (python.org or the Company Portal) with "Add to PATH"'
        $py = $null
    }
}
if (-not $py) {
    if (-not $real) { Report 'FAIL' 'Python' 'python is not on PATH' 'install Python 3.9+ (python.org or the Company Portal) with "Add to PATH"' }
} else {
    $ver = (& python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null)
    $ok = (& python -c "import sys; print(sys.version_info >= (3, 9))" 2>$null)
    if ($ok -eq 'True') { Report 'PASS' 'Python' "$ver ($($py.Source))" } else { Report 'FAIL' 'Python' "${ver}: pbik needs 3.9 or newer" 'Python 3.9+ (python.org or the Company Portal)' }

    $wheels = Join-Path $root 'tools\wheels'
    $offlineHow = "pbik needs no packages (python tools\pbik\pbik.py runs from the repo). For jsonschema: on a machine with access, python -m pip download jsonschema -d wheels --only-binary :all:, copy the folder to tools\wheels, then python -m pip install --user --no-index --find-links tools\wheels jsonschema"
    $pip = (& python -m pip --version 2>$null)
    if ($LASTEXITCODE -eq 0 -and $pip) { Report 'PASS' 'pip' ($pip -split ' from ')[0] }
    else { Report 'WARN' 'pip' 'not available' $offlineHow }

    # pip access: can pip reach its index (proxy, firewall, or a company mirror in pip.ini)?
    if ($pip -and -not $Offline) {
        $cfg = (& python -m pip config list 2>$null) -join '; '
        $tmpdl = Join-Path $env:TEMP 'pbik-doctor-pip'
        $idx = Run-WithTimeout { param($d) & python -m pip download --no-deps --only-binary :all: -d $d --quiet --timeout 20 jsonschema 2>&1; "exit=$LASTEXITCODE" } @($tmpdl)
        Remove-Item -Recurse -Force $tmpdl -ErrorAction SilentlyContinue
        if ($idx -and ($idx | Select-Object -Last 1) -eq 'exit=0') {
            Report 'PASS' 'pip index access' ("reached the package index" + $(if ($cfg) { " ($cfg)" } else { '' }))
        } elseif (Test-Path (Join-Path $wheels '*.whl')) {
            Report 'PASS' 'pip offline install' "no index access, but tools\wheels has $(@(Get-ChildItem $wheels -Filter *.whl).Count) wheel(s): python -m pip install --user --no-index --find-links tools\wheels jsonschema"
        } else {
            $why = if ($idx) { (($idx | Where-Object { $_ -notmatch '^exit=' } | Select-Object -Last 1) -as [string]) } else { 'timed out' }
            Report 'WARN' 'pip index access' "pip can't download packages ($("$why".Trim()))" ("behind a proxy set HTTPS_PROXY or pip.ini [global] proxy / index-url (ask IT for the company mirror). Otherwise " + $offlineHow)
        }
    }
    $usersite = (& python -c "import site, os; p = site.getusersitepackages(); d = p`nwhile not os.path.exists(d): d = os.path.dirname(d)`nprint(p, os.access(d, os.W_OK))" 2>$null)
    if ($usersite -match 'True$') { Report 'PASS' 'pip --user location' (($usersite -replace ' True$', '') + ' (writable)') }
    elseif ($usersite) { Report 'WARN' 'pip --user location' (($usersite -replace ' False$', '') + ' is not writable') 'skip pip install -e tools\pbik: run python tools\pbik\pbik.py from the repo' }

    $js = (& python -c "import jsonschema; print(jsonschema.__version__)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $js) { Report 'PASS' 'jsonschema' "$js (optional)" }
    else { Report 'WARN' 'jsonschema' 'not installed (optional)' "pbik validate skips the schema checks only; install it later (pip install --user jsonschema, or offline from tools\wheels)" }

    $pbik = Join-Path $root 'tools\pbik\pbik.py'
    $pv = (& python $pbik --version 2>$null)
    if ($LASTEXITCODE -eq 0 -and $pv) { Report 'PASS' 'pbik' $pv } else { Report 'FAIL' 'pbik' "python $pbik --version failed" 'nothing for IT: rerun from a full copy of the kit (git clone)' }

    $cache = Join-Path $root 'tools\pbik\schemas'
    if (Test-Path $cache) { Report 'PASS' 'pbik schema cache' "$(@(Get-ChildItem $cache -Recurse -Filter *.json).Count) schema file(s)" }
    else { Report 'WARN' 'pbik schema cache' 'empty' 'pbik validate skips the schema checks; fetch once with network: python tools\pbik\pbik.py schemas fetch <Name>.Report (or copy tools\pbik\schemas from another machine)' }
    $proj = Join-Path $root 'design\specs\project.json'
    $catName = 'home'
    if (Test-Path $proj) { $pj = Get-Content $proj -Raw | ConvertFrom-Json; if ($pj.catalog) { $catName = $pj.catalog } }
    $cat = Join-Path $root "tools\pbik\catalogs\$catName.json"
    if (Test-Path $cat) { Report 'PASS' 'settings catalog' "tools\pbik\catalogs\$catName.json" }
    else { Report 'WARN' 'settings catalog' "tools\pbik\catalogs\$catName.json missing" "pbik validate skips the catalog check; build one: pbik catalog refresh --name $catName <Desktop-saved folders> (docs/UPDATE-ROUTINE.md)" }
}

# ---------------------------------------------------------------- PowerShell execution policy
# Ignoring this process's own -ExecutionPolicy; and whether a local script really runs (pbi-bridge.ps1, run-dax.ps1)
$scopes = Get-ExecutionPolicy -List
$list = ($scopes | ForEach-Object { "$($_.Scope)=$($_.ExecutionPolicy)" }) -join ', '
$eff = ($scopes | Where-Object { $_.Scope -ne 'Process' -and "$($_.ExecutionPolicy)" -ne 'Undefined' } | Select-Object -First 1).ExecutionPolicy
if (-not $eff) { $eff = 'Restricted' }
$gpo = $scopes | Where-Object { $_.Scope -in 'MachinePolicy', 'UserPolicy' -and "$($_.ExecutionPolicy)" -ne 'Undefined' }
$probe = Join-Path $env:TEMP 'pbik-doctor-probe.ps1'
Set-Content -Path $probe -Value "Write-Output 'pbik-probe-ok'" -Encoding ASCII
$inherited = $env:PSExecutionPolicyPreference                  # a parent's -ExecutionPolicy Bypass would hide the policy
$env:PSExecutionPolicyPreference = $null
$ran = (& powershell -NoProfile -File $probe 2>$null)
$env:PSExecutionPolicyPreference = $inherited
$ranBypass = (& powershell -NoProfile -ExecutionPolicy Bypass -File $probe 2>$null)
Remove-Item $probe -Force -ErrorAction SilentlyContinue
if ($ran -eq 'pbik-probe-ok') {
    Report 'PASS' 'Execution policy' "$eff ($list): local scripts run"
} elseif ($ranBypass -eq 'pbik-probe-ok') {
    Report 'WARN' 'Execution policy' "$eff ($list): local scripts run only with -ExecutionPolicy Bypass" 'pbik passes -ExecutionPolicy Bypass itself; start doctor and run-dax.ps1 with powershell -ExecutionPolicy Bypass -File ...'
} else {
    $who = if ($gpo) { 'set by Group Policy' } else { 'set on this machine' }
    Report 'FAIL' 'Execution policy' "$eff ($list): local .ps1 scripts are blocked even with Bypass ($who)" 'allow local scripts for this user (RemoteSigned at CurrentUser, or Bypass for powershell -File); pbik desktop and run-dax.ps1 need them'
}

# ---------------------------------------------------------------- Node.js, npx, npm registry (MCP servers)
$node = Get-Command node -ErrorAction SilentlyContinue
$npx = Get-Command npx -ErrorAction SilentlyContinue
$npmOk = $false
$npxCache = Join-Path $env:LOCALAPPDATA 'npm-cache\_npx'
$mcpCached = @(Get-ChildItem $npxCache -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'node_modules\@microsoft\powerbi-modeling-mcp\package.json') })
$daxCached = @(Get-ChildItem $npxCache -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'node_modules\@daxlib\mcp\package.json') })
if (-not $node) {
    Report 'WARN' 'Node.js' 'node is not on PATH' 'the modeling MCP and daxlib-mcp start through npx: see the Modeling MCP and DAX Lib lines below'
} else {
    $nv = (& node --version 2>$null)
    $major = [int](("$nv" -replace '^v', '') -split '\.')[0]
    if ($major -ge 18) { Report 'PASS' 'Node.js' "$nv ($($node.Source))" }
    else { Report 'WARN' 'Node.js' "${nv}: daxlib-mcp needs 18 or newer" 'ask IT for Node.js 18+ (LTS), or use the DAX Lib and Modeling MCP fallbacks below' }
}
if ($node -and -not $npx) { Report 'WARN' 'npx' 'npx is not on PATH (it comes with npm)' 'reinstall Node.js with npm, or use the fallbacks below' }
elseif ($npx) { Report 'PASS' 'npx' $npx.Source }
if ($npx -and -not $Offline) {
    $reg = (& npm config get registry 2>$null)
    $nv2 = Run-WithTimeout { & npm view '@daxlib/mcp@0.1.0' version --fetch-timeout=20000 --fetch-retries=0 2>&1; "exit=$LASTEXITCODE" } @()
    $npmOk = [bool]($nv2 -and ($nv2 | Select-Object -Last 1) -eq 'exit=0')
    if ($npmOk) { Report 'PASS' 'npm registry access' "reached $reg" }
    else { Report 'WARN' 'npm registry access' "npm can't reach $reg$(if (-not $nv2) { ' (timed out)' })" 'DAX Lib from the vendored copy (design/udf/vendored.py); ask IT for registry.npmjs.org or a company npm mirror (npm config set registry <url>)' }
}
# Modeling MCP: the only route for model changes (CLAUDE.md). npx fetches @latest on start, or runs the cached copy.
if ($mcpCached.Count -gt 0) {
    $mv = (Get-Content (Join-Path $mcpCached[0].FullName 'node_modules\@microsoft\powerbi-modeling-mcp\package.json') -Raw | ConvertFrom-Json).version
    Report 'PASS' 'Modeling MCP' "@microsoft/powerbi-modeling-mcp $mv in the npx cache"
} elseif ($npx -and ($npmOk -or $Offline)) {
    Report 'PASS' 'Modeling MCP' 'not cached yet; npx downloads it at the first session'
} else {
    Report 'FAIL' 'Modeling MCP' 'no npx, or npm registry blocked, and not in the npx cache' 'Node.js 18+ with access to @microsoft/powerbi-modeling-mcp on the npm registry (or a mirror); in VS Code, Microsoft''s Power BI Modeling MCP extension. /model can''t change the model without it'
}
$udfVendored = Test-Path (Join-Path $root 'design\udf\vendor\NOTICE.md')
if ($daxCached.Count -gt 0 -or ($npx -and $npmOk)) {
    Report 'PASS' 'DAX Lib (daxlib-mcp)' $(if ($daxCached.Count -gt 0) { '@daxlib/mcp in the npx cache' } else { 'npx can fetch @daxlib/mcp@0.1.0' })
} elseif ($npx -and $Offline) {
    Report 'PASS' 'DAX Lib (daxlib-mcp)' 'npx present (registry not checked: -Offline)'
} elseif ($udfVendored) {
    Report 'WARN' 'DAX Lib (daxlib-mcp)' 'daxlib-mcp can''t start here' 'install from the vendored copy through the modeling MCP (design/udf/README.md "When npm is blocked")'
} else {
    Report 'FAIL' 'DAX Lib (daxlib-mcp)' 'daxlib-mcp can''t start and design/udf/vendor is missing' 'npm registry access, or restore design/udf/vendor from the kit'
}

# ---------------------------------------------------------------- Power BI Desktop, level 1702, Bridge, Deneb
$pinned = $null
$vfile = Join-Path $root 'VERSIONS.md'
if (Test-Path $vfile) {
    $m = Select-String -Path $vfile -Pattern '\| Power BI Desktop \| ([\d.]+)' | Select-Object -First 1
    if ($m) { $pinned = $m.Matches[0].Groups[1].Value }
}
$store = Get-AppxPackage -Name '*PowerBI*' -ErrorAction SilentlyContinue | Sort-Object Version -Descending | Select-Object -First 1
$dver = $null; $where = ''
if ($store) { $dver = "$($store.Version)"; $where = 'Microsoft Store' } else {
    $exe = @("$env:ProgramFiles\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
             "${env:ProgramFiles(x86)}\Microsoft Power BI Desktop\bin\PBIDesktop.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($exe) { $dver = (Get-Item $exe).VersionInfo.ProductVersion; $where = $exe }
    if ($dver -match '^\s*(\d+(\.\d+){1,3})') { $dver = $Matches[1] }   # MSI: '2.155.756.0 (26.06)+<hash>'
}
if (-not $dver) { Report 'FAIL' 'Power BI Desktop' 'not found (Store package or Program Files install)' 'Power BI Desktop (Microsoft Store or Company Portal); the version VERSIONS.md names, or newer' }
elseif ($pinned -and -not $dver.StartsWith($pinned)) { Report 'WARN' 'Power BI Desktop' "$dver ($where); VERSIONS.md was tested with $pinned" 'run /update (record it, regression suite, /smoke) before building; set targetDesktop in design/specs/project.json if it is older' }
else { Report 'PASS' 'Power BI Desktop' ("$dver ($where)" + $(if ($pinned) { ', as in VERSIONS.md' } else { '' })) }

# Compatibility level 1702 (DAX user-defined functions, so DAX Lib): Desktop 2.147 (September 2025) and later
if ($dver) {
    $minor = [int](($dver -split '\.')[1])
    $levels = @(Get-ChildItem $root -Directory -Filter '*.SemanticModel' -ErrorAction SilentlyContinue | ForEach-Object {
        $db = Join-Path $_.FullName 'definition\database.tmdl'
        if (Test-Path $db) { $l = Select-String -Path $db -Pattern 'compatibilityLevel:\s*(\d+)' | Select-Object -First 1; if ($l) { "$($_.Name) $($l.Matches[0].Groups[1].Value)" } } })
    $lv = if ($levels) { "; models here: $($levels -join ', ')" } else { '' }
    if ($minor -ge 147) { Report 'PASS' 'Compatibility level 1702' "Desktop $dver supports it (DAX user-defined functions, from 2.147 / September 2025)$lv" }
    else { Report 'WARN' 'Compatibility level 1702' "Desktop $dver is older than 2.147 (September 2025): no DAX user-defined functions$lv" 'no DAX Lib: write SVG measures by hand (.claude/rules/svg.md); ask IT for a Desktop update' }
}

# Desktop Bridge: through pbik (exit 3 = bridge not available)
$manualReload = 'manual reload in the /build click list: File > Close without saving, reopen the .pbip; screenshots by hand (.claude/rules/pbik.md "When the Desktop Bridge is missing")'
$pipe = [IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -match 'pbi-desktop-bridge-\d+$' }
if (-not $pipe) {
    Report 'WARN' 'Desktop Bridge' 'no Desktop open with the bridge (open a .pbip in Desktop with the bridge preview feature on, and rerun)' $manualReload
} elseif ($py) {
    $st = (& python (Join-Path $root 'tools\pbik\pbik.py') desktop state 2>&1)
    if ($LASTEXITCODE -eq 3) { Report 'WARN' 'Desktop Bridge' "pipe found but pbik can't use it: $((($st | Select-Object -Last 1) -as [string]).Trim())" $manualReload }
    else { Report 'PASS' 'Desktop Bridge' "$(@($pipe).Count) instance(s); pbik desktop state answers (exit $LASTEXITCODE)" }
}

# Deneb (certified AppSource custom visual): Desktop's own policy, and the project setting. The tenant admin setting
# can't be read from here.
$denebFallback = 'set "customVisuals": false in design/specs/project.json: pbik build then builds every Deneb visual''s native or SVG fallback'
$pol = @('HKLM:\Software\Policies\Microsoft\Power BI Desktop', 'HKCU:\Software\Policies\Microsoft\Power BI Desktop') |
    ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } | Where-Object { $_ }
$cvOff = $pol | Where-Object { $_.EnableCustomVisuals -eq 0 }
$projCv = $null
if (Test-Path $proj) { $projCv = (Get-Content $proj -Raw | ConvertFrom-Json).customVisuals }
if ($projCv -eq $false) {
    Report 'PASS' 'Deneb' 'project.json customVisuals false: pbik build builds the fallbacks'
} elseif ($cvOff) {
    Report 'WARN' 'Deneb' 'custom visuals are turned off by Desktop policy (EnableCustomVisuals = 0)' $denebFallback
} else {
    Report 'PASS' 'Deneb' 'not blocked by Desktop policy (the tenant setting can still block it: if Deneb doesn''t load in Desktop, use the fallback)'
}

# ---------------------------------------------------------------- Git
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Report 'FAIL' 'Git' 'git is not on PATH' 'Git for Windows (git-scm.com or the Company Portal): the kit commits after each step' }
else {
    $gn = (& git config user.name 2>$null); $ge = (& git config user.email 2>$null)
    if ($gn -and $ge) { Report 'PASS' 'Git' "$((& git --version) -replace 'git version ', '') ($gn)" }
    else { Report 'WARN' 'Git' "$((& git --version) -replace 'git version ', ''); user.name or user.email not set" 'git config --global user.name "<name>"; git config --global user.email "<work email>"' }
}

# ---------------------------------------------------------------- network and folders
$proxy = @('HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY') | Where-Object { [Environment]::GetEnvironmentVariable($_) } | ForEach-Object { "$_ set" }
$winhttp = (netsh winhttp show proxy 2>$null | Select-String -Pattern 'Proxy Server|Direct access' | Select-Object -First 1)
Report 'PASS' 'Proxy' (((@($proxy) + @("$winhttp".Trim())) | Where-Object { $_ }) -join '; ')
if ($root -match 'OneDrive') {
    Report 'WARN' 'Kit folder' "$root is in a OneDrive-synced folder" 'move the kit outside OneDrive (sync can lock files while Desktop saves), or pause sync while building'
} else { Report 'PASS' 'Kit folder' $root }

# Copilot files (work laptops may have GitHub Copilot instead of Claude Code)
if ($py) {
    $cp = (& python (Join-Path $root 'tools\copilot\sync.py') --check 2>&1)
    if ($LASTEXITCODE -eq 0) { Report 'PASS' 'Copilot files' (($cp | Select-Object -Last 1) -as [string]) }
    else { Report 'WARN' 'Copilot files' 'out of step with .claude/commands or CLAUDE.md' 'python tools\copilot\sync.py' }
}

Write-Host ''
if ($fails) { Write-Host "NO-GO: $fails check(s) failed, $warns with a fallback. Send docs/IT-REQUEST.md with the FAIL lines." -ForegroundColor Red; exit 1 }
elseif ($warns) { Write-Host "GO with fallbacks: $warns warning(s); each names its fallback." -ForegroundColor Yellow }
else { Write-Host 'GO: every check passed.' -ForegroundColor Green }
