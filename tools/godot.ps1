# Runs the Godot .NET editor from pipeline/local.settings.jsonc ("godotExe") with any arguments.
# Prefers the _console variant next to it, so output is readable and the exit code comes back.
#
#   pwsh -NoProfile -File tools/godot.ps1 --headless --path game -- --smoke-frames=600
. "$PSScriptRoot/LocalSettings.ps1"

$exe = Get-LocalSetting 'godotExe'
$console = $exe -replace '\.exe$', '_console.exe'
if (Test-Path $console) { $exe = $console }

$forward = Get-ForwardedArgs $PSCommandPath $args
& $exe @forward
exit $LASTEXITCODE
