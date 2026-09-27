$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$python = if ($env:LMW_BUILD_PYTHON) { [System.IO.Path]::GetFullPath($env:LMW_BUILD_PYTHON) } else { Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing project virtual environment' }
$localesData = (Join-Path $projectRoot 'app\i18n\locales') + ';app/i18n/locales'
$runtimeIcons = @('app_icon.ico','app_icon_128.png','dropdown_dark.svg','dropdown_light.svg')
$themesData = (Join-Path $projectRoot 'app\themes\dark.qss') + ';app/themes'
$iconFile = Join-Path $projectRoot 'assets\icons\app_icon.ico'
$versionFile = Join-Path $projectRoot 'tools\version_info.txt'
$launcherFile = Join-Path $projectRoot 'tools\launcher.py'
$originalPath = $env:PATH
$env:PATH = (Split-Path $python) + ';' + (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
$builderArgs = @('-m','PyInstaller',$launcherFile,'--noconfirm','--onedir','--windowed',
  '--name','LinksMangaWorkspace','--contents-directory','runtime',
  '--distpath','dist/0.6.0-final','--workpath','build/0.6.0-final','--specpath','build/0.6.0-final',
  '--icon',$iconFile,'--version-file',$versionFile,
  '--add-data',$localesData,'--add-data',$themesData,
  '--collect-all','rapidocr','--collect-all','pypdfium2','--hidden-import','PySide6.QtSvg',
  '--collect-all','onnxruntime','--exclude-module','pymupdf','--exclude-module','fitz',
  '--exclude-module','torch','--exclude-module','transformers','--exclude-module','tensorflow',
  '--exclude-module','paddle','--paths',$projectRoot)
foreach ($asset in $runtimeIcons) {
  $builderArgs += @('--add-data', ((Join-Path $projectRoot ('assets\icons\' + $asset)) + ';assets/icons'))
}
if ($env:LMW_BUILD_INCREMENTAL -ne '1') { $builderArgs += '--clean' }
& $python @builderArgs
$buildExitCode = $LASTEXITCODE
$env:PATH = $originalPath
if ($buildExitCode -ne 0) { throw 'PyInstaller failed' }
$releaseDir = Join-Path $projectRoot 'dist\0.6.0-final\Links Manga Studio'
$builtDir = Join-Path $projectRoot 'dist\0.6.0-final\LinksMangaWorkspace'
if (Test-Path -LiteralPath $releaseDir) {
  $resolved = [System.IO.Path]::GetFullPath($releaseDir)
  if (-not $resolved.StartsWith([System.IO.Path]::GetFullPath($projectRoot + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe release path' }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}
Move-Item -LiteralPath $builtDir -Destination $releaseDir
& $python tools/collect_licenses.py (Join-Path $releaseDir 'licenses')
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
Copy-Item -LiteralPath LICENSE,NOTICE,QUICK_START.md,USER_GUIDE.md,THIRD_PARTY_NOTICES.md,MODEL_LICENSES.md,LICENSE_REVIEW.md -Destination $releaseDir
Copy-Item -LiteralPath 'docs/PORTABLE_README.md' -Destination (Join-Path $releaseDir 'README.md')
Copy-Item -LiteralPath 'docs/PORTABLE_README.zh-CN.md' -Destination (Join-Path $releaseDir 'README.zh-CN.md')
Copy-Item -LiteralPath 'docs/USER_GUIDE.zh-CN.md' -Destination (Join-Path $releaseDir 'USER_GUIDE.zh-CN.md')
$zip = Join-Path $projectRoot 'dist\Links-Manga-Studio-0.6.0-windows-x64.zip'
if (Test-Path -LiteralPath $zip) {
  $historyDir = Join-Path $projectRoot 'dist\history'
  $backupPath = Join-Path $historyDir ('Links-Manga-Studio-0.6.0-previous-' + [guid]::NewGuid().ToString('N') + '.zip')
  foreach ($target in @($zip,$backupPath)) {
    if (-not [System.IO.Path]::GetFullPath($target).StartsWith([System.IO.Path]::GetFullPath($projectRoot + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe ZIP history path' }
  }
  New-Item -ItemType Directory -Path $historyDir -Force | Out-Null
  Move-Item -LiteralPath $zip -Destination $backupPath
  Write-Output ('Previous ZIP preserved: ' + $backupPath)
}
Compress-Archive -LiteralPath $releaseDir -DestinationPath $zip
$sha = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
Set-Content -LiteralPath ($zip + '.sha256') -Value ($sha + '  ' + [System.IO.Path]::GetFileName($zip)) -Encoding ascii
Write-Output $zip
