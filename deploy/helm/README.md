# Ezra Helm chart

Deploys **Ezra Core** (the REST API + Redis hot tier + Qdrant warm tier) to any
Kubernetes cluster. The cold tier is **MongoDB Atlas** (managed, external) — you
supply its connection string.

## Quick start (portable — any cluster)

```bash
helm install ezra ./deploy/helm/ezra \
  --namespace ezra --create-namespace \
  --set image.repository=YOUR_REGISTRY/ezra-api \
  --set image.tag=latest \
  --set llm.provider=gemini \
  --set secrets.values.mongodbUri='mongodb+srv://USER:PASS@cluster.mongodb.net/?retryWrites=true' \
  --set secrets.values.llmApiKey='YOUR_GEMINI_KEY'
```

Until a public image is published, build + push your own:

```bash
docker build -f deploy/docker/Dockerfile -t YOUR_REGISTRY/ezra-api:latest .
docker push YOUR_REGISTRY/ezra-api:latest
```

## GKE (keyless Vertex + Secret Manager)

```bash
helm install ezra ./deploy/helm/ezra -n ezra --create-namespace \
  --set image.repository=REGION-docker.pkg.dev/PROJECT/ezra/ezra-api \
  --set llm.provider=vertex --set llm.vertex.project=PROJECT \
  --set serviceAccount.annotations."iam\.gke\.io/gcp-service-account"=ezra-runtime@PROJECT.iam.gserviceaccount.com \
  --set secrets.backend=gcpSecretManager \
  --set secrets.gcpSecretManager.project=PROJECT
```

This path needs the GKE **Secret Manager add-on** + **Workload Identity** on the
cluster, the secrets pre-created in Secret Manager, and the GSA granted
`roles/aiplatform.user`. (The `install.sh` installer and `deploy/terraform/` set
all of that up.)

## Key values

| Value | Default | Notes |
|---|---|---|
| `image.repository` / `.tag` | `ghcr.io/xavio2495/ezra-api` / appVersion | the Ezra Core image |
| `llm.provider` | `vertex` | `vertex` (keyless on GKE) or `gemini` (API key) |
| `llm.vertex.project` | — | required for `provider=vertex` |
| `secrets.backend` | `kubernetes` | `kubernetes` · `existing` · `gcpSecretManager` |
| `secrets.values.mongodbUri` | — | **required** — your Atlas URI |
| `redis.enabled` / `qdrant.enabled` | `true` | disable + set `.url` to use external instances |
| `service.type` | `LoadBalancer` | or `ClusterIP` + `ingress.enabled=true` |

See `values.yaml` for the full surface. Verify a render without installing:

```bash
helm template ezra ./deploy/helm/ezra \
  --set secrets.values.mongodbUri=mongodb://x --set llm.vertex.project=x
```
