# Run Terraform in a container (no local install), keyless via the host gcloud
# access token. Usage:  .\deploy\scripts\tf.ps1 init|plan|apply|destroy|output ...
#   .\deploy\scripts\tf.ps1 init
#   .\deploy\scripts\tf.ps1 apply
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $TfArgs)

$ErrorActionPreference = "Stop"
$token = (gcloud auth print-access-token).Trim()
$tfDir = (Resolve-Path (Join-Path $PSScriptRoot "..\terraform")).Path

docker run --rm -i `
  -e "GOOGLE_OAUTH_ACCESS_TOKEN=$token" `
  -v "${tfDir}:/wd" -w /wd `
  hashicorp/terraform:latest @TfArgs
