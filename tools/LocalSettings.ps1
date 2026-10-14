# Shared helper: reads pipeline/local.settings.jsonc so tool wrappers never hard-code a path.
# Dot-source it:  . "$PSScriptRoot/LocalSettings.ps1"

function Get-LocalSetting([string]$Name) {
    $file = Join-Path $PSScriptRoot '..\pipeline\local.settings.jsonc'
    if (-not (Test-Path $file)) {
        throw "Missing $file. Copy pipeline/local.settings.example.jsonc to it and fix the paths."
    }
    # PowerShell 7's ConvertFrom-Json accepts // comments, so JSONC parses as-is.
    $value = (Get-Content $file -Raw | ConvertFrom-Json).$Name
    if (-not $value) { throw "'$Name' is not set in $file." }
    if (-not (Test-Path $value)) { throw "'$Name' points at '$value', which doesn't exist. Fix it in $file." }
    return $value
}

# The arguments after the script, exactly as typed. `pwsh -File` splits any argument that
# starts with "-" and contains ":" (so --screenshot=user://shot.png arrives as two), so read
# the raw command line when we were started that way. Called from a PowerShell prompt
# instead, the script isn't on the process command line and $Fallback ($args) is correct.
function Get-ForwardedArgs([string]$ScriptPath, [object[]]$Fallback) {
    $all = [Environment]::GetCommandLineArgs()
    $name = Split-Path $ScriptPath -Leaf
    for ($i = 0; $i -lt $all.Length; $i++) {
        if ((Split-Path $all[$i] -Leaf) -eq $name) {
            if ($i -ge $all.Length - 1) { return @() }
            # The leading comma keeps a single argument an array; a bare string would splat per character.
            return , @($all[($i + 1)..($all.Length - 1)])
        }
    }
    return , @($Fallback)
}
