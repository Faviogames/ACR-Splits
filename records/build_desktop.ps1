$ErrorActionPreference = 'Stop'
$recordsRoot = $PSScriptRoot
$version = '0.7.0'
$dist = Join-Path $recordsRoot 'dist'
$payload = Join-Path $dist 'payload'
New-Item -ItemType Directory -Path $dist,$payload -Force | Out-Null
dotnet publish (Join-Path $recordsRoot 'desktop/ACRModRecords.csproj') -c Release -r win-x64 --self-contained true -p:Version=$version -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:DebugType=None -p:IncludeNativeLibrariesForSelfExtract=true -o $payload
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
$pythonZip = Join-Path $recordsRoot 'build-tools/python-3.14.0-embed-amd64.zip'
if (!(Test-Path $pythonZip)) { throw 'Download official Python 3.14.0 Windows embeddable x64 archive to build-tools first' }
Expand-Archive $pythonZip (Join-Path $payload 'python') -Force
@('python314.zip','.','..','import site') | Set-Content (Join-Path $payload 'python/python314._pth') -Encoding ascii
$modules = Join-Path $payload 'records'
New-Item -ItemType Directory -Path $modules -Force | Out-Null
foreach ($name in @('__init__.py','app.py','capture.py','inspect_save.py','match_result.py','online.py')) { Copy-Item (Join-Path $recordsRoot $name) $modules -Force }
Copy-Item (Join-Path $recordsRoot 'ui') $modules -Recurse -Force
$catalog = Join-Path $recordsRoot 'stages.json'
if (!(Test-Path $catalog)) { $catalog = Join-Path $recordsRoot 'website/public/data/stages.json' }
Copy-Item $catalog (Join-Path $modules 'stages.json') -Force
Compress-Archive -Path (Join-Path $payload '*') -DestinationPath (Join-Path $dist 'payload.zip') -Force
dotnet publish (Join-Path $recordsRoot 'installer/Installer.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:DebugType=None -p:IncludeNativeLibrariesForSelfExtract=true -o (Join-Path $dist 'setup')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed' }
Copy-Item (Join-Path $dist 'setup/ACR-Splits-Setup.exe') (Join-Path $dist 'ACR-Splits-Setup.exe') -Force
$digest = (Get-FileHash (Join-Path $dist 'ACR-Splits-Setup.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
"$digest  ACR-Splits-Setup.exe" | Set-Content (Join-Path $dist 'SHA256SUMS.txt') -Encoding ascii
Write-Output "Built $version : $digest"

