# Build the production API image and push it to Artifact Registry.
#   .\deploy\scripts\build-push.ps1            # tag = short git sha
#   .\deploy\scripts\build-push.ps1 -Tag v1
[CmdletBinding()]
param(
  [string] $Tag = (git rev-parse --short HEAD),
  [string] $Region = "us-east1",
  [string] $Project = "ezra-498021",
  [string] $Repo = "ezra"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$registry = "$Region-docker.pkg.dev/$Project/$Repo"
$image = "$registry/ezra-api:$Tag"

gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet
docker build -f "$root\deploy\docker\Dockerfile" -t $image -t "$registry/ezra-api:latest" $root
docker push $image
docker push "$registry/ezra-api:latest"

Write-Output $image
