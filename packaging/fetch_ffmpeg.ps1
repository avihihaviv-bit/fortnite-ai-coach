# Download a pinned ffmpeg build for Windows into vendor\ffmpeg and verify its SHA-256.
#
# Source: Gyan.dev "full" build mirrored on GitHub (GyanD/codexffmpeg). The full build includes
# ddagrab (Desktop Duplication capture), NVENC, AMF, QSV and libx264, which the recorder needs.
#
# Hash verification, in order of preference:
#   1. packaging\ffmpeg.sha256 (pinned in the repository)  <- preferred
#   2. $env:FFMPEG_SHA256
#   3. the SHA-256 digest GitHub publishes for the release asset
# If none is available the script stops. After a successful run it prints the hash so it can be pinned.
param(
    [string]$Version = "7.1.1",
    [string]$Dest = "$PSScriptRoot\..\vendor\ffmpeg"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$asset = "ffmpeg-$Version-full_build.zip"
$url = "https://github.com/GyanD/codexffmpeg/releases/download/$Version/$asset"
$tmp = Join-Path $env:TEMP $asset

$pinned = ""
$pinFile = Join-Path $PSScriptRoot "ffmpeg.sha256"
if (Test-Path $pinFile) { $pinned = (Get-Content $pinFile -Raw).Trim().ToLower() }
if (-not $pinned -and $env:FFMPEG_SHA256) { $pinned = $env:FFMPEG_SHA256.Trim().ToLower() }
if (-not $pinned) {
    Write-Host "No pinned hash; reading the digest GitHub publishes for $asset"
    $headers = @{ "User-Agent" = "fortnite-ai-coach-build" }
    if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }
    $rel = Invoke-RestMethod -Headers $headers "https://api.github.com/repos/GyanD/codexffmpeg/releases/tags/$Version"
    $a = $rel.assets | Where-Object { $_.name -eq $asset }
    if ($a -and $a.digest -like "sha256:*") { $pinned = $a.digest.Substring(7).ToLower() }
}
if (-not $pinned) { throw "No SHA-256 available to verify $asset. Pin it in packaging\ffmpeg.sha256." }

Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $tmp
$actual = (Get-FileHash $tmp -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $pinned) { Remove-Item $tmp; throw "SHA-256 mismatch for $asset`n expected $pinned`n actual   $actual" }
Write-Host "SHA-256 verified: $actual"

$extract = Join-Path $env:TEMP "ffmpeg-extract-$Version"
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive $tmp -DestinationPath $extract
$root = Get-ChildItem $extract -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $root.FullName "bin\ffmpeg.exe") $Dest -Force
Copy-Item (Join-Path $root.FullName "bin\ffprobe.exe") $Dest -Force
Copy-Item (Join-Path $root.FullName "LICENSE") (Join-Path $Dest "FFMPEG_LICENSE.txt") -Force
Remove-Item $tmp, $extract -Recurse -Force
& (Join-Path $Dest "ffmpeg.exe") -hide_banner -version | Select-Object -First 1
Write-Host "To pin this build, put this line in packaging\ffmpeg.sha256:"
Write-Host $actual
