# Download a fixed ffmpeg build for Windows into vendor\ffmpeg and verify its SHA-256.
#
# Source: Gyan.dev "full" build mirrored on GitHub (GyanD/codexffmpeg). The full build includes
# ddagrab (Desktop Duplication capture), NVENC, AMF, QSV and libx264, which the recorder needs.
#
# Version + hash, in order of preference:
#   1. packaging\ffmpeg.sha256 pinned in the repository: "<version> <sha256>"   <- preferred
#   2. the first version from $Candidates whose GitHub release asset has a published SHA-256 digest
#   3. otherwise the .sha256 file Gyan.dev publishes for that exact package (independent second source)
# Nothing is ever extracted without a matching hash. The script prints the line to pin.
param(
    [string[]]$Candidates = @("8.0.1", "8.0", "7.1.2", "7.1.1"),
    [string]$Dest = "$PSScriptRoot\..\vendor\ffmpeg"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$headers = @{ "User-Agent" = "fortnite-ai-coach-build" }
if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }

function Get-ReleaseDigest([string]$v) {
    try {
        $rel = Invoke-RestMethod -Headers $headers "https://api.github.com/repos/GyanD/codexffmpeg/releases/tags/$v"
    } catch { return $null }
    $a = $rel.assets | Where-Object { $_.name -eq "ffmpeg-$v-full_build.zip" }
    if (-not $a) { return $null }
    if ($a.digest -like "sha256:*") { return $a.digest.Substring(7).ToLower() }
    try {  # independent source: the builder's own checksum file
        $txt = (Invoke-WebRequest -UseBasicParsing "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-$v-full_build.zip.sha256").Content
        $h = ([string]$txt).Trim().Split()[0].ToLower()
        if ($h -match '^[0-9a-f]{64}$') { return $h }
    } catch { }
    return $null
}

$version = ""; $expected = ""
$pinFile = Join-Path $PSScriptRoot "ffmpeg.sha256"
if (Test-Path $pinFile) {
    $parts = (Get-Content $pinFile -Raw).Trim().Split()
    if ($parts.Count -ge 2) { $version = $parts[0]; $expected = $parts[1].ToLower() }
}
if (-not $expected) {
    foreach ($v in $Candidates) {
        $h = Get-ReleaseDigest $v
        Write-Host "Candidate ${v}: $(if ($h) { 'hash available' } else { 'no release or no published hash' })"
        if ($h) { $version = $v; $expected = $h; break }
    }
}
if (-not $expected) { throw "No verifiable ffmpeg build found. Pin '<version> <sha256>' in packaging\ffmpeg.sha256." }

$asset = "ffmpeg-$version-full_build.zip"
$url = "https://github.com/GyanD/codexffmpeg/releases/download/$version/$asset"
$tmp = Join-Path $env:TEMP $asset
Write-Host "Downloading $url"
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $tmp
$actual = (Get-FileHash $tmp -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $expected) { Remove-Item $tmp; throw "SHA-256 mismatch for $asset`n expected $expected`n actual   $actual" }
Write-Host "SHA-256 verified: $actual"

$extract = Join-Path $env:TEMP "ffmpeg-extract-$version"
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive $tmp -DestinationPath $extract
$root = Get-ChildItem $extract -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item (Join-Path $root.FullName "bin\ffmpeg.exe") $Dest -Force
Copy-Item (Join-Path $root.FullName "bin\ffprobe.exe") $Dest -Force
Copy-Item (Join-Path $root.FullName "LICENSE") (Join-Path $Dest "FFMPEG_LICENSE.txt") -Force
Remove-Item $tmp, $extract -Recurse -Force
& (Join-Path $Dest "ffmpeg.exe") -hide_banner -version | Select-Object -First 1
Write-Host "PIN-THIS: $version $actual"
