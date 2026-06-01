# Push secret values from .env into Secret Manager (one version each).
# Secrets must already exist (created by Terraform). Values never touch git or
# Terraform state. A bearer token is generated if the .env value is blank.
#   .\deploy\scripts\bootstrap-secrets.ps1
[CmdletBinding()]
param(
  [string] $Project = "ezra-498021",
  [string] $EnvFile = (Join-Path $PSScriptRoot "..\..\.env")
)

$ErrorActionPreference = "Stop"

function Get-EnvValue([string] $name) {
  $line = Select-String -Path $EnvFile -Pattern "^$name=" -SimpleMatch:$false | Select-Object -First 1
  if ($null -eq $line) { return "" }
  return ($line.Line -replace "^$name=", "").Trim()
}

function Set-Secret([string] $secretId, [string] $value) {
  if ([string]::IsNullOrWhiteSpace($value)) {
    Write-Warning "skipping $secretId — value is empty"
    return
  }
  $tmp = New-TemporaryFile
  try {
    [System.IO.File]::WriteAllText($tmp.FullName, $value)  # no trailing newline / BOM
    gcloud secrets versions add $secretId --project $Project --data-file="$($tmp.FullName)" | Out-Null
    Write-Output "added version to $secretId"
  } finally {
    Remove-Item $tmp.FullName -Force
  }
}

$mongo = Get-EnvValue "EZRA_MONGODB_URI"
$llm = Get-EnvValue "EZRA_LLM_API_KEY"
$bearer = Get-EnvValue "EZRA_API_BEARER_TOKEN"
if ([string]::IsNullOrWhiteSpace($bearer) -or $bearer -eq "dev-token-change-me") {
  $bearer = [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
  Write-Output "generated a new API bearer token (store it from Secret Manager if you need it)"
}

Set-Secret "ezra-mongodb-uri" $mongo
Set-Secret "ezra-llm-api-key" $llm
Set-Secret "ezra-api-bearer-token" $bearer
