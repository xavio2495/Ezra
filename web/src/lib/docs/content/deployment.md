# Deployment

Ezra Core and the agent fleet deploy on **Google Kubernetes Engine (GKE)**, keyless via Workload Identity Federation. (The original plan named Cloud Run; GKE was chosen to fit the dynamically-spawning multi-agent fleet, the Secret Manager CSI driver, and keyless WIF.) Three ways to stand it up, fastest first.

## 1. One-command installer

An interactive script that detects your environment and sets up either local dev or a full GKE deploy (it creates the runtime service account, provisions the foundation, builds + pushes the image, and — after a cost confirmation — creates the cluster and deploys):

```bash
curl -fsSL https://ezra128.vercel.app/install.sh | bash
```

It's `curl|bash`-safe (prompts read from your terminal), needs no public image (it builds yours), and never creates billable resources without an explicit yes.

## 2. Helm

If you already have a cluster, install the chart directly:

```bash
helm install ezra ./deploy/helm/ezra --namespace ezra --create-namespace \
  --set image.repository=YOUR_REGISTRY/ezra-api \
  --set llm.provider=gemini \
  --set secrets.values.mongodbUri='mongodb+srv://…' \
  --set secrets.values.llmApiKey='…'
```

The chart bundles Redis + Qdrant (toggle off to use external), supports portable Kubernetes secrets or the GKE Secret Manager CSI path, and Vertex (keyless) or an API-key LLM. See `deploy/helm/README.md` for the full values surface.

## 3. Terraform + kustomize (manual)

The lowest-level path — `deploy/terraform/` for the GCP foundation + cluster, `deploy/k8s/` for the manifests, driven by the scripts in `deploy/scripts/`. See `deploy/README.md`.

## Topology

- **`ezra-api`** — the FastAPI surface (`ezra_core.api.asgi:app`), backed by live Atlas.
- **`redis`** + **`qdrant`** — hot and warm tiers, in-cluster.
- **Agent fleet** — ADK agents (one image, `Dockerfile.agents`, no torch — uses the Gemini-backed checker) consuming Ezra via `EzraToolset` over `RemoteEzraService`.
- Manifests live in `deploy/k8s/` (kustomize); one-off Jobs (ingest, smokes) are applied on demand and not part of the kustomization.

## Keyless auth (Workload Identity Federation)

Service-account JSON keys are org-blocked. Instead:

- A Kubernetes SA (`ezra/ezra-api`) impersonates the GSA `ezra-ai-developer` via GKE Workload Identity.
- **LLM on GKE = Vertex AI** (`vertex_ai/gemini-2.5-flash`), keyless — AI Studio keys are rejected from GCP egress. Set `GOOGLE_GENAI_USE_VERTEXAI=true` plus the Vertex project/location.
- **Secrets** (Atlas URI, API keys, bearer token) come from **Secret Manager via the CSI driver** (`secrets-store-gke.csi.k8s.io`), mounted as files under `/mnt/secrets-store` and read into `EZRA_*` env at startup (`secret_files.py`).

## Atlas access

The runtime self-serves its egress IP onto the Atlas access list via the Admin API (`atlas_access.ensure_egress_allowed`) before connecting — no manual IP whitelisting, and never `0.0.0.0/0`. Code that talks to Atlas directly (not via `Ezra.from_settings`) must call it explicitly.

## ADK service objects

Ezra registers as a first-class ADK service:

- **`EzraToolset(BaseToolset)`** — the full surface (recall / query / snapshot / commit + rewind / revert / replay / branch) as ADK `FunctionTool`s. `get_tools` is **async** (ADK awaits it).
- **`EzraMemoryService(BaseMemoryService)`** — `add_session_to_memory` → warm tier; `search_memory` → warm recall + archival as `MemoryEntry`.

For Gemini models, use ADK's **native** path (bare model id + `GOOGLE_GENAI_USE_VERTEXAI=true`), not `LiteLlm` — the latter tool-calls unreliably for Gemini.

## Cost control

The cluster scales to **0 nodes** when idle:

```bash
gcloud container clusters resize ezra --node-pool=primary --num-nodes=0 --zone us-east1-c
```

Scale back up to run the fleet or a Job, then back to 0. CD on the `release` branch builds the images in GitHub Actions and deploys via the keyless WIF chain.

See `deploy/README.md` for the full manifest set, Terraform foundation, and the build/deploy scripts.
