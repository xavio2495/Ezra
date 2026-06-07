# Ezra — GCP / GKE deployment

Production target is **GKE** (Workload Identity, keyless). Redis (hot) and Qdrant
(warm) run in-cluster from the same images as dev; MongoDB is **Atlas** (managed);
secrets live in **Secret Manager** and are read via the GKE Secret Manager add-on
under Workload Identity. No service-account JSON keys anywhere — SA-key creation
is org-blocked, so auth is WIF / the host's user credentials.

```
deploy/
├── docker/Dockerfile        # production API image (uv --no-dev, uvicorn)
├── terraform/               # GCP infra: APIs, Artifact Registry, Secret Manager, IAM/WIF, GKE (gated)
├── k8s/                     # namespace, KSA, configmap, SecretProviderClass, redis, qdrant, ezra-api, kustomization
└── scripts/                 # PowerShell: tf, bootstrap-secrets, build-push, deploy
```

## Prerequisites

- Docker Desktop running (Terraform + kubectl-less steps run in containers).
- `gcloud` authorized on the host (`gcloud auth login`), project `ezra-498021`.
- Terraform auth is keyless: `deploy/scripts/tf.ps1` injects
  `GOOGLE_OAUTH_ACCESS_TOKEN` from `gcloud auth print-access-token`.
- For the cluster steps only: `kubectl` + `gke-gcloud-auth-plugin`
  (`gcloud components install kubectl gke-gcloud-auth-plugin`).

## 1. Provision the foundation (no cluster yet)

`create_cluster` defaults to **false**, so this enables APIs and creates the
Artifact Registry repo, Secret Manager secrets, and the IAM/WIF bindings — all
free/cheap, no GKE bill.

```powershell
cp deploy\terraform\terraform.tfvars.example deploy\terraform\terraform.tfvars
.\deploy\scripts\tf.ps1 init
.\deploy\scripts\tf.ps1 apply        # review plan, then approve
```

## 2. Push secret values

Secrets are created empty by Terraform; push values from your `.env`:

```powershell
.\deploy\scripts\bootstrap-secrets.ps1
```

(`ezra-mongodb-uri`, `ezra-llm-api-key`, `ezra-api-bearer-token` — a bearer token
is generated if `.env` has none.)

## 3. Build & push the API image

```powershell
.\deploy\scripts\build-push.ps1      # tags with the short git sha + latest
```

## 4. Create the cluster, then deploy (when ready — costs credits)

```powershell
# flip the gate
notepad deploy\terraform\terraform.tfvars   # create_cluster = true
.\deploy\scripts\tf.ps1 apply

# build + push + apply manifests + roll out
.\deploy\scripts\deploy.ps1
```

`deploy.ps1` prints the LoadBalancer external IP. Health check:

```powershell
curl http://<EXTERNAL_IP>/ezra/health
```

## Notes

- **State** is local (`deploy/terraform/*.tfstate`, gitignored). For shared/CI
  use, switch to a GCS backend in `versions.tf`.
- **Runtime identity** is the existing `ezra-ai-developer` GSA (swap via the
  `runtime_gsa_email` variable). The KSA `ezra/ezra-api` impersonates it.
- **`claude-docs/HANDOFF.md`** Session 6 mentions Cloud Run; the chosen production target is
  GKE (recorded in `claude-docs/MEMORY.md`). This tree builds for GKE.
- The demo agents (GEAP Agent Runtime) are out of scope here — this deploys
  Ezra Core (the REST API + tiers). Add agent-runtime wiring in Session 6.
