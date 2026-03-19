param ([string]$file_path)

Push-Location $PSScriptRoot

Remove-Item *.abi, *.bin -ErrorAction Ignore
$normalizedPath = $file_path.TrimStart('/','\')
docker run -v "${PWD}:/sources" ethereum/solc:0.8.19 -o /sources/ --abi --bin "/sources/$normalizedPath"

$fileNameWithoutExt = [System.IO.Path]::GetFileNameWithoutExtension($normalizedPath)
$abiPath = Join-Path $PSScriptRoot "$fileNameWithoutExt.abi"
$binPath = Join-Path $PSScriptRoot "$fileNameWithoutExt.bin"
$artifactPath = Join-Path $PSScriptRoot "$fileNameWithoutExt.artifact.json"

if (!(Test-Path $abiPath) -or !(Test-Path $binPath)) {
    throw "Compilation output not found for '$file_path'."
}

$abi = Get-Content -Raw -Path $abiPath | ConvertFrom-Json
$bin = (Get-Content -Raw -Path $binPath).Trim()
$artifact = [ordered]@{
    abi = $abi
    bin = "0x$bin"
}
$artifact | ConvertTo-Json -Depth 100 -Compress | Set-Content -NoNewline -Path $artifactPath

Pop-Location
