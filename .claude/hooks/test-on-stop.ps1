# Stop hook: when Claude finishes a turn with uncommitted changes to Core, tests or data,
# run the logic tests. On failure, exit 2 so Claude sees the output and keeps working.
#
# Skips when nothing relevant changed, or when the same changes already passed (stamp file).
# If tests still fail after Claude was sent back once (stop_hook_active), it lets the turn end
# and only warns, so a stubborn failure can't loop forever.
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $root

try { $hookInput = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { $hookInput = $null }
$paths = @('src', 'tests', 'game/data')

# Fingerprint of everything relevant that differs from HEAD, including untracked files.
$diff = (git -c core.safecrlf=false diff HEAD -- @paths 2>$null) -join "`n"
$untracked = @(git ls-files --others --exclude-standard -- @paths 2>$null)
if (-not $diff -and -not $untracked) { exit 0 }
$untrackedHashes = if ($untracked) { (git hash-object -- @untracked) -join "`n" } else { '' }
$bytes = [Text.Encoding]::UTF8.GetBytes("$diff`n$($untracked -join "`n")`n$untrackedHashes")
$fingerprint = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))

$stamp = Join-Path $PSScriptRoot '.last-test-pass'
if ((Test-Path $stamp) -and "$(Get-Content $stamp -Raw)".Trim() -eq $fingerprint) { exit 0 }

$output = dotnet test tests/Core.Tests --nologo 2>&1 | Out-String
if ($LASTEXITCODE -eq 0) {
    Set-Content $stamp $fingerprint -NoNewline
    exit 0
}

$tail = ($output -split "`r?`n" | Where-Object { $_ -match '\S' -and $_ -notmatch '^\s+at ' } | Select-Object -Last 60) -join "`n"
if ($hookInput.stop_hook_active) {
    # Already sent back once; surface it to the user instead of looping.
    @{ systemMessage = "dotnet test is still failing after Claude's last attempt. Check the test output." } |
        ConvertTo-Json -Compress
    exit 0
}
[Console]::Error.WriteLine("dotnet test tests/Core.Tests failed. Fix it before finishing:`n$tail")
exit 2
