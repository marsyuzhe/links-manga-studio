$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$python = if ($env:LMW_BUILD_PYTHON) { [System.IO.Path]::GetFullPath($env:LMW_BUILD_PYTHON) } else { Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing project virtual environment' }
$localesData = (Join-Path $projectRoot 'app\i18n\locales') + ';app/i18n/locales'
$iconsData = (Join-Path $projectRoot 'assets\icons') + ';assets/icons'
$themesData = (Join-Path $projectRoot 'app\themes\dark.qss') + ';app/themes'
$iconFile = Join-Path $projectRoot 'assets\icons\app_icon.ico'
$versionFile = Join-Path $projectRoot 'tools\version_info.txt'
$launcherFile = Join-Path $projectRoot 'tools\launcher.py'
$originalPath = $env:PATH
$env:PATH = (Split-Path $python) + ';' + (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name LinksMangaWorkspace --contents-directory runtime `
  --distpath dist --workpath build --specpath build `
  --icon $iconFile --version-file $versionFile `
  --add-data $localesData `
  --add-data $iconsData `
  --add-data $themesData `
  --collect-all rapidocr --collect-all pypdfium2 `
  --collect-all onnxruntime --exclude-module pymupdf --exclude-module fitz `
  --paths $projectRoot $launcherFile
$buildExitCode = $LASTEXITCODE
$env:PATH = $originalPath
if ($buildExitCode -ne 0) { throw 'PyInstaller failed' }
$releaseDir = Join-Path $projectRoot 'dist\Links Manga Studio'
$builtDir = Join-Path $projectRoot 'dist\LinksMangaWorkspace'
if (Test-Path -LiteralPath $releaseDir) {
  $resolved = [System.IO.Path]::GetFullPath($releaseDir)
  if (-not $resolved.StartsWith([System.IO.Path]::GetFullPath($projectRoot + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe release path' }
  Remove-Item -LiteralPath $resolved -Recurse -Force
}
Move-Item -LiteralPath $builtDir -Destination $releaseDir
& $python tools/collect_licenses.py (Join-Path $releaseDir 'licenses')
Copy-Item -LiteralPath LICENSE,NOTICE,README.md,README.zh-CN.md,USER_GUIDE.md,USER_ACCEPTANCE_TEST.md,RELEASE_NOTES.md,RELEASE_NOTES.zh-CN.md,CHANGELOG.md,ROADMAP.md,THIRD_PARTY_NOTICES.md,MODEL_LICENSES.md,LICENSE_REVIEW.md -Destination $releaseDir
New-Item -ItemType Directory -Path (Join-Path $releaseDir 'docs') -Force | Out-Null
Copy-Item -LiteralPath 'docs/USER_ACCEPTANCE_0.5.0.md' -Destination (Join-Path $releaseDir 'docs')
Copy-Item -LiteralPath CONTRIBUTING.md,SECURITY.md -Destination $releaseDir
Copy-Item -LiteralPath 'docs/ARCHITECTURE.md','docs/MANUAL_GITHUB_PUBLISH.md','docs/GITHUB_RELEASE_CHECKLIST.md' -Destination (Join-Path $releaseDir 'docs')
Copy-Item -LiteralPath 'docs/images' -Destination (Join-Path $releaseDir 'docs') -Recurse
$snapshotDir = Join-Path $releaseDir 'docs/ui_snapshots/0.5.0'
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null
Copy-Item -LiteralPath 'docs/ui_snapshots/0.5.0/font_browser.png','docs/ui_snapshots/0.5.0/quality_check.png' -Destination $snapshotDir
$zip = Join-Path $projectRoot 'dist\Links-Manga-Studio-0.5.0-windows-x64.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -LiteralPath $releaseDir -DestinationPath $zip
Write-Output $zip
