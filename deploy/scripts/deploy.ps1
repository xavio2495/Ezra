# Full deploy: build+push the image, point kubectl at the GKE cluster, apply the
# manifests, and roll the API to the new image. Requires the cluster to exist
# (terraform apply with create_cluster=true) and kubectl + the
# gke-gcloud-auth-plugin on PATH (gcloud components install kubectl
# gke-gcloud-auth-plugin).
#   .\deploy\scripts\deploy.ps1
[CmdletBinding()]
param(
  [string] $Tag = (git rev-parse --short HEAD),
  [string] $Region = "us-east1",
  [string] $Zone = "us-east1-c",
  [string] $Project = "ezra-498021",
  [string] $Repo = "ezra",
  [string] $Cluster = "ezra"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$registry = "$Region-docker.pkg.dev/$Project/$Repo"

& "$PSScriptRoot\build-push.ps1" -Tag $Tag -Region $Region -Project $Project -Repo $Repo | Out-Null

gcloud container clusters get-credentials $Cluster --zone $Zone --project $Project
kubectl apply -k "$root\deploy\k8s"
kubectl -n ezra set image deployment/ezra-api "ezra-api=$registry/ezra-api:$Tag"
kubectl -n ezra rollout status deployment/ezra-api --timeout=180s

Write-Output "Deployed $registry/ezra-api:$Tag"
Write-Output "External IP:"
kubectl -n ezra get service ezra-api -o "jsonpath={.status.loadBalancer.ingress[0].ip}"
