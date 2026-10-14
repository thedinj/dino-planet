# Runs Blender from pipeline/local.settings.jsonc ("blenderExe") with any arguments.
#
#   pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_cleanup.py -- --in ... --out ...
. "$PSScriptRoot/LocalSettings.ps1"

$exe = Get-LocalSetting 'blenderExe'
$forward = Get-ForwardedArgs $PSCommandPath $args
& $exe @forward
exit $LASTEXITCODE
