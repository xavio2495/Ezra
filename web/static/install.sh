#!/usr/bin/env bash
# ============================================================================
#  Ezra installer — interactive setup for local dev or Google Kubernetes Engine.
#
#    curl -fsSL https://ezra128.vercel.app/install.sh | bash
#    # or the GitHub raw URL:
#    curl -fsSL https://raw.githubusercontent.com/xavio2495/ezra/main/web/static/install.sh | bash
#
#  Detects your environment (OS, tools, GCP) and walks you through either:
#    • Local dev   — Redis + Qdrant via Docker, a bundled Mongo or your Atlas URI,
#                    and a .env wizard. Nothing leaves your machine.
#    • Deploy GKE  — provisions Artifact Registry / Secret Manager / IAM (free),
#                    builds + pushes the API image, then (with confirmation) the
#                    GKE cluster, and deploys Ezra Core. Creates billable resources
#                    only after you confirm.
#
#  Override defaults with env vars: EZRA_REPO, EZRA_DIR, EZRA_REF.
#  Re-run any time — it won't clobber an existing .env without asking.
# ============================================================================
set -euo pipefail

EZRA_REPO="${EZRA_REPO:-https://github.com/xavio2495/ezra.git}"
EZRA_REF="${EZRA_REF:-main}"
EZRA_DIR="${EZRA_DIR:-$HOME/ezra}"
DEFAULT_REGION="us-east1"
DEFAULT_ZONE="us-east1-c"
VERTEX_LOCATION="us-central1"   # Vertex model availability

# --- pretty output (color only on a tty) ---------------------------------------
if [ -t 1 ]; then
  B=$(printf '\033[1m'); DIM=$(printf '\033[2m'); R=$(printf '\033[0m')
  C=$(printf '\033[36m'); G=$(printf '\033[32m'); Y=$(printf '\033[33m'); RED=$(printf '\033[31m')
else B=; DIM=; R=; C=; G=; Y=; RED=; fi

say()  { printf '%s\n' "$*"; }
step() { printf '\n%s==>%s %s%s%s\n' "$C" "$R" "$B" "$*" "$R"; }
ok()   { printf '%s  ✓%s %s\n' "$G" "$R" "$*"; }
warn() { printf '%s  !%s %s\n' "$Y" "$R" "$*"; }
die()  { printf '%s  ✗ %s%s\n' "$RED" "$*" "$R" >&2; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }

ask() { # var prompt [default]
  local __v="$1" prompt="$2" def="${3:-}" ans
  if [ -n "$def" ]; then printf '%s%s%s [%s]: ' "$B" "$prompt" "$R" "$def"; else printf '%s%s%s: ' "$B" "$prompt" "$R"; fi
  read -r ans || true
  printf -v "$__v" '%s' "${ans:-$def}"
}
ask_secret() { # var prompt
  local __v="$1" prompt="$2" ans
  printf '%s%s%s: ' "$B" "$2" "$R"; read -rs ans || true; echo
  printf -v "$__v" '%s' "$ans"
}
confirm() { local a; printf '%s%s%s [y/N] ' "$B" "$1" "$R"; read -r a || true; [[ "${a:-}" =~ ^[Yy] ]]; }

gen_token() {
  if has openssl; then openssl rand -hex 24
  else head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}

# ============================================================================
#  Detect
# ============================================================================
banner() {
  printf '%s\n' "$C$B"
  cat <<'ART'
    ███████ ███████ ██████   █████  
    ██         ███  ██   ██ ██   ██ 
    █████     ███   ██████  ███████ 
    ██       ███    ██   ██ ██   ██ 
    ███████ ███████ ██   ██ ██   ██                             
ART
  printf '%s\n' "$R"
}

detect() {
  OS="$(uname -s)"; ARCH="$(uname -m)"
  case "$OS" in Linux|Darwin) : ;; *) die "Unsupported OS: $OS (Linux/macOS only; on Windows use WSL2 or the PowerShell scripts in deploy/scripts)";; esac
  has git || die "git is required. Install it and re-run."

  HAS_DOCKER=false; has docker && docker info >/dev/null 2>&1 && HAS_DOCKER=true
  HAS_GCLOUD=false; has gcloud && HAS_GCLOUD=true
  HAS_KUBECTL=false; has kubectl && HAS_KUBECTL=true
  HAS_TF=false; has terraform && HAS_TF=true
  ON_GCP=false
  if curl -fsS -m 1 -H 'Metadata-Flavor: Google' http://metadata.google.internal/ >/dev/null 2>&1; then ON_GCP=true; fi

  GCLOUD_ACCT=""; GCLOUD_PROJECT=""
  if $HAS_GCLOUD; then
    GCLOUD_ACCT="$(gcloud config get-value account 2>/dev/null || true)"
    GCLOUD_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
  fi

  step "Environment"
  say "  OS / arch     : ${OS} / ${ARCH}$( $ON_GCP && echo '  (running on GCP)')"
  say "  Docker        : $( $HAS_DOCKER && echo "${G}ready${R}" || echo "${Y}not running${R}")"
  say "  gcloud        : $( $HAS_GCLOUD && echo "${G}${GCLOUD_ACCT:-authed} / ${GCLOUD_PROJECT:-no project}${R}" || echo "${Y}not installed${R}")"
  say "  kubectl / tf  : $( $HAS_KUBECTL && echo -n 'kubectl ' )$( $HAS_TF && echo -n 'terraform' )$( $HAS_KUBECTL || $HAS_TF || echo "${Y}neither (only needed for GKE)${R}")"
}

# ============================================================================
#  Repo
# ============================================================================
acquire_repo() {
  if [ -f "ezra_core/runtime.py" ] && [ -d "deploy/k8s" ]; then
    REPO="$(pwd)"; ok "Using the Ezra repo in the current directory: $REPO"; return
  fi
  if [ -d "$EZRA_DIR/.git" ]; then
    step "Updating existing checkout at $EZRA_DIR"
    git -C "$EZRA_DIR" fetch --quiet origin "$EZRA_REF" || true
    git -C "$EZRA_DIR" checkout --quiet "$EZRA_REF" || true
    git -C "$EZRA_DIR" pull --quiet --ff-only || warn "could not fast-forward; using the local checkout"
  else
    step "Cloning Ezra → $EZRA_DIR"
    git clone --quiet --branch "$EZRA_REF" "$EZRA_REPO" "$EZRA_DIR" || die "clone failed ($EZRA_REPO @ $EZRA_REF)"
  fi
  REPO="$EZRA_DIR"; ok "Repo ready at $REPO"
}

# ============================================================================
#  .env helpers
# ============================================================================
set_env() { # key value...  (handles '=' inside values, e.g. Atlas URIs)
  local key="$1"; shift; local val="$*"
  touch "$ENV_FILE"
  grep -vE "^${key}=" "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null || true
  printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"
}
get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true; }

# ============================================================================
#  Local dev
# ============================================================================
local_flow() {
  $HAS_DOCKER || die "Docker isn't running. Start Docker Desktop / the daemon and re-run."
  cd "$REPO"
  ENV_FILE="$REPO/.env"
  [ -f .env.example ] && [ ! -f .env ] && cp .env.example .env && ok "created .env from .env.example"

  step "Cold tier (MongoDB)"
  say "  1) Bundle a local MongoDB container  ${DIM}(zero-config; note: no Atlas Vector Search)${R}"
  say "  2) Use my MongoDB Atlas connection string  ${DIM}(matches production)${R}"
  local choice; ask choice "Choose" "1"
  local extra_services="redis qdrant"
  if [ "$choice" = "2" ]; then
    local uri; ask uri "Paste your EZRA_MONGODB_URI (mongodb+srv://…)"
    [ -n "$uri" ] || die "an Atlas URI is required for option 2"
    set_env EZRA_MONGODB_URI "$uri"
  else
    cat > "$REPO/docker-compose.override.yml" <<'YAML'
# Generated by install.sh — a local MongoDB for zero-config dev.
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    ports: ["27017:27017"]
    volumes: ["ezra_mongo:/data/db"]
volumes:
  ezra_mongo: {}
YAML
    set_env EZRA_MONGODB_URI "mongodb://mongo:27017/ezra"
    extra_services="redis qdrant mongo"
    ok "added a local mongo service (docker-compose.override.yml)"
    warn "local Mongo has no \$vectorSearch — per-turn archival vector recall is a no-op locally"
  fi

  step "Language model"
  local model key
  ask model "LLM model (litellm id)" "$(get_env EZRA_LLM_MODEL || echo gemini/gemini-3.5-flash)"
  set_env EZRA_LLM_MODEL "$model"
  ask_secret key "Gemini API key (EZRA_LLM_API_KEY, blank to skip)"
  [ -n "$key" ] && set_env EZRA_LLM_API_KEY "$key"
  set_env EZRA_EMBEDDING_MODEL "$(get_env EZRA_EMBEDDING_MODEL || echo gemini/gemini-embedding-001)"

  local bearer; bearer="$(get_env EZRA_API_BEARER_TOKEN || true)"
  if [ -z "$bearer" ] || [ "$bearer" = "dev-token-change-me" ]; then set_env EZRA_API_BEARER_TOKEN "$(gen_token)"; ok "generated an API bearer token"; fi
  set_env EZRA_REDIS_URL "redis://redis:6379"
  set_env EZRA_QDRANT_URL "http://qdrant:6333"

  step "Starting infrastructure"
  docker compose up -d $extra_services
  ok "Redis + Qdrant$( [ "$choice" = "1" ] && echo ' + Mongo') are up"

  step "You're set."
  cat <<EOF
  Run the test suite:     ${B}docker compose run --rm app uv run --frozen pytest -q tests/unit${R}
  Open a dev shell:       ${B}docker compose run --rm app bash${R}
  Run an example:         ${B}docker compose run --rm app uv run --frozen python -m examples.basic_chat${R}
  Config lives in:        ${B}${ENV_FILE}${R}
  Docs:                   ${B}https://ezra128.vercel.app/docs${R}
EOF
}

# ============================================================================
#  GKE deploy
# ============================================================================
run_tf() { ( cd "$REPO/deploy/terraform" && GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)" terraform "$@" ); }

gke_flow() {
  $HAS_GCLOUD || die "gcloud is required for the GKE path. Install the Google Cloud SDK and run 'gcloud auth login'."
  $HAS_DOCKER || die "Docker is required to build the Ezra image (no public image yet)."
  $HAS_TF     || die "terraform is required for the GKE path. Install it (https://terraform.io/downloads) and re-run."
  $HAS_KUBECTL|| die "kubectl is required for the GKE path. Install it and re-run."
  [ -n "$GCLOUD_ACCT" ] || die "gcloud is not authenticated. Run: gcloud auth login"

  step "Target project"
  ask PROJECT "GCP project id" "${GCLOUD_PROJECT}"
  [ -n "$PROJECT" ] || die "a project id is required"
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null || true)"
  [ -n "$PROJECT_NUMBER" ] || die "can't read project $PROJECT — check the id and your permissions"
  ask REGION "Region" "$DEFAULT_REGION"
  ask ZONE   "Zone"   "$DEFAULT_ZONE"
  CLUSTER="ezra"; REPO_AR="ezra"; NS="ezra"; KSA="ezra-api"
  REGISTRY="${REGION}-docker.pkg.dev/${PROJECT}/${REPO_AR}"
  GSA="ezra-runtime@${PROJECT}.iam.gserviceaccount.com"

  step "Cold tier + secrets"
  ask MONGO_URI "MongoDB Atlas connection string (EZRA_MONGODB_URI)"
  [ -n "$MONGO_URI" ] || die "an Atlas URI is required (GKE has no local Mongo)"
  local atlas_pub="" atlas_priv=""
  if confirm "Add Atlas Admin API keys so Ezra auto-allowlists the cluster egress IP? (recommended)"; then
    ask_secret atlas_pub  "Atlas API public key (EZRA_MONGODB_PUBLIC_KEY)"
    ask_secret atlas_priv "Atlas API private key (EZRA_MONGODB_PRIVATE_KEY)"
  fi

  step "Language model"
  say "  GKE runs keyless via ${B}Vertex AI${R} (recommended — AI Studio keys are blocked from GCP egress)."
  local llm_mode="vertex" llm_key=""
  if ! confirm "Use Vertex AI (keyless Workload Identity)?"; then
    llm_mode="key"; ask_secret llm_key "Gemini API key (EZRA_LLM_API_KEY)"
    warn "AI Studio keys commonly 403 from GCP egress — Vertex is strongly recommended."
  fi

  # Secret set is built from the choices so the SecretProviderClass + Terraform agree.
  SECRETS=(ezra-mongodb-uri ezra-api-bearer-token)
  [ "$llm_mode" = "key" ] && SECRETS+=(ezra-llm-api-key)
  [ -n "$atlas_pub" ] && SECRETS+=(ezra-mongodb-public-key ezra-mongodb-private-key)

  step "Plan"
  cat <<EOF
  Project        ${B}${PROJECT}${R} (#${PROJECT_NUMBER})
  Region / zone  ${REGION} / ${ZONE}
  Registry       ${REGISTRY}/ezra-api
  Runtime GSA    ${GSA}
  LLM            ${llm_mode}$( [ "$llm_mode" = vertex ] && echo " (vertex_ai/gemini-2.5-flash @ ${VERTEX_LOCATION})")
  Secrets        ${SECRETS[*]}
  Cluster        ${CLUSTER} (created only after an explicit confirm)
EOF
  confirm "Proceed with the FREE foundation (APIs, Artifact Registry, Secret Manager, IAM)?" || { warn "aborted"; return; }

  step "Enabling core APIs"
  gcloud services enable container.googleapis.com artifactregistry.googleapis.com \
    secretmanager.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com compute.googleapis.com \
    $( [ "$llm_mode" = vertex ] && echo aiplatform.googleapis.com ) --project "$PROJECT" --quiet
  ok "APIs enabled"

  step "Runtime service account"
  if ! gcloud iam service-accounts describe "$GSA" --project "$PROJECT" >/dev/null 2>&1; then
    gcloud iam service-accounts create ezra-runtime --project "$PROJECT" --display-name "Ezra Runtime" --quiet
    ok "created $GSA"
  else ok "$GSA already exists"; fi
  if [ "$llm_mode" = vertex ]; then
    gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:${GSA}" \
      --role roles/aiplatform.user --condition=None --quiet >/dev/null
    ok "granted roles/aiplatform.user (Vertex)"
  fi

  step "Terraform — foundation (no cluster yet)"
  local tfvars="$REPO/deploy/terraform/terraform.tfvars"
  {
    echo "project_id          = \"$PROJECT\""
    echo "project_number      = \"$PROJECT_NUMBER\""
    echo "region              = \"$REGION\""
    echo "zone                = \"$ZONE\""
    echo "runtime_gsa_email   = \"$GSA\""
    echo "create_cluster      = false"
    echo "enable_demo_bigquery = false"
    printf 'secret_ids = [%s]\n' "$(printf '"%s", ' "${SECRETS[@]}" | sed 's/, $//')"
  } > "$tfvars"
  run_tf init -input=false >/dev/null
  run_tf apply -input=false -auto-approve
  ok "foundation provisioned"

  step "Pushing secret values to Secret Manager"
  put_secret() { printf '%s' "$2" | gcloud secrets versions add "$1" --project "$PROJECT" --data-file=- --quiet >/dev/null && ok "set $1"; }
  put_secret ezra-mongodb-uri "$MONGO_URI"
  put_secret ezra-api-bearer-token "$(gen_token)"
  [ "$llm_mode" = key ] && put_secret ezra-llm-api-key "$llm_key"
  [ -n "$atlas_pub" ]  && put_secret ezra-mongodb-public-key "$atlas_pub"
  [ -n "$atlas_priv" ] && put_secret ezra-mongodb-private-key "$atlas_priv"

  step "Building + pushing the API image"
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
  local tag; tag="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo latest)"
  docker build -f "$REPO/deploy/docker/Dockerfile" -t "${REGISTRY}/ezra-api:${tag}" -t "${REGISTRY}/ezra-api:latest" "$REPO"
  docker push "${REGISTRY}/ezra-api:${tag}"; docker push "${REGISTRY}/ezra-api:latest"
  ok "pushed ${REGISTRY}/ezra-api:${tag}"

  step "Create the GKE cluster?"
  warn "This creates a billable GKE cluster (${CLUSTER}, ${ZONE}). You can delete it later with: gcloud container clusters delete ${CLUSTER} --zone ${ZONE}"
  confirm "Create the cluster now?" || { say "Foundation + image are ready. To deploy later: set create_cluster=true in $tfvars, terraform apply, then re-run this installer."; return; }
  sed -i.bak 's/create_cluster      = false/create_cluster      = true/' "$tfvars" && rm -f "$tfvars.bak"
  run_tf apply -input=false -auto-approve
  ok "cluster up"

  step "Deploying Ezra Core"
  deploy_to_cluster "$tag"

  step "Done."
  local ip; ip="$(kubectl -n "$NS" get service ezra-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
  if [ -n "$ip" ]; then ok "LoadBalancer IP: $ip"; say "  Health: ${B}curl http://${ip}/ezra/health${R}"
  else warn "LoadBalancer IP still pending — check: kubectl -n $NS get svc ezra-api"; fi
}

deploy_to_cluster() { # tag
  local tag="$1"
  # token kubeconfig — no gke-gcloud-auth-plugin needed
  local ep ca kc
  ep="$(gcloud container clusters describe "$CLUSTER" --zone "$ZONE" --project "$PROJECT" --format='value(endpoint)')"
  ca="$(gcloud container clusters describe "$CLUSTER" --zone "$ZONE" --project "$PROJECT" --format='value(masterAuth.clusterCaCertificate)')"
  kc="$(mktemp)"
  cat > "$kc" <<EOF
apiVersion: v1
kind: Config
clusters:
- name: ezra
  cluster: { server: "https://${ep}", certificate-authority-data: "${ca}" }
contexts:
- name: ezra
  context: { cluster: ezra, user: ezra }
current-context: ezra
users:
- name: ezra
  user: { token: "$(gcloud auth print-access-token)" }
EOF
  export KUBECONFIG="$kc"

  # Generate a project-specific overlay (the repo manifests are pinned to the demo project).
  local ov; ov="$(mktemp -d)"
  cp "$REPO/deploy/k8s/namespace.yaml" "$REPO/deploy/k8s/redis.yaml" "$REPO/deploy/k8s/qdrant.yaml" "$REPO/deploy/k8s/ezra-api.yaml" "$ov/"

  cat > "$ov/serviceaccount.yaml" <<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ${KSA}
  namespace: ${NS}
  annotations:
    iam.gke.io/gcp-service-account: ${GSA}
EOF

  { # configmap
    cat <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: ezra-config
  namespace: ${NS}
data:
  EZRA_REDIS_URL: "redis://redis:6379"
  EZRA_QDRANT_URL: "http://qdrant:6333"
  EZRA_MONGODB_DB: "ezra"
  EZRA_API_PORT: "8080"
  EZRA_TRACING_ENABLED: "false"
EOF
    if [ "$llm_mode" = vertex ]; then cat <<EOF
  EZRA_LLM_MODEL: "vertex_ai/gemini-2.5-flash"
  EZRA_META_AGENT_MODEL: "vertex_ai/gemini-2.5-flash"
  EZRA_EMBEDDING_MODEL: "vertex_ai/text-embedding-005"
  GOOGLE_GENAI_USE_VERTEXAI: "true"
  GOOGLE_CLOUD_PROJECT: "${PROJECT}"
  GOOGLE_CLOUD_LOCATION: "${VERTEX_LOCATION}"
  VERTEXAI_PROJECT: "${PROJECT}"
  VERTEXAI_LOCATION: "${VERTEX_LOCATION}"
EOF
    else cat <<EOF
  EZRA_LLM_MODEL: "gemini/gemini-3.5-flash"
  EZRA_META_AGENT_MODEL: "gemini/gemini-3.5-flash"
  EZRA_EMBEDDING_MODEL: "gemini/gemini-embedding-001"
EOF
    fi
  } > "$ov/configmap.yaml"

  { # secretproviderclass — only the secrets we actually populated
    cat <<EOF
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: ezra-secrets
  namespace: ${NS}
spec:
  provider: gke
  parameters:
    secrets: |
EOF
    for s in "${SECRETS[@]}"; do
      printf '      - resourceName: "projects/%s/secrets/%s/versions/latest"\n        path: "%s"\n' "$PROJECT" "$s" "$s"
    done
  } > "$ov/secretproviderclass.yaml"

  cat > "$ov/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - serviceaccount.yaml
  - configmap.yaml
  - secretproviderclass.yaml
  - redis.yaml
  - qdrant.yaml
  - ezra-api.yaml
images:
  - name: ezra-api
    newName: ${REGISTRY}/ezra-api
    newTag: ${tag}
EOF

  kubectl apply -k "$ov"
  kubectl -n "$NS" rollout status deployment/ezra-api --timeout=240s
  rm -rf "$ov"
}

# ============================================================================
#  Menu
# ============================================================================
menu() {
  step "What would you like to do?"
  say "  1) Set up Ezra locally (Docker)$( $HAS_DOCKER || echo "  ${Y}— Docker not running${R}")"
  say "  2) Deploy Ezra to GKE$( $HAS_GCLOUD || echo "  ${Y}— gcloud not installed${R}")"
  say "  3) Configure only (write .env, no services)"
  say "  q) Quit"
  local c; ask c "Choose" "1"
  case "$c" in
    1) acquire_repo; local_flow ;;
    2) acquire_repo; gke_flow ;;
    3) acquire_repo; ENV_FILE="$REPO/.env"; cd "$REPO"; [ -f .env.example ] && [ ! -f .env ] && cp .env.example .env
       local_env_only ;;
    q|Q) say "Bye."; exit 0 ;;
    *) die "unknown choice: $c" ;;
  esac
}

local_env_only() {
  step "Configure .env"
  local uri model key
  ask uri "EZRA_MONGODB_URI (blank to skip)"; [ -n "$uri" ] && set_env EZRA_MONGODB_URI "$uri"
  ask model "EZRA_LLM_MODEL" "gemini/gemini-3.5-flash"; set_env EZRA_LLM_MODEL "$model"
  ask_secret key "EZRA_LLM_API_KEY (blank to skip)"; [ -n "$key" ] && set_env EZRA_LLM_API_KEY "$key"
  [ -z "$(get_env EZRA_API_BEARER_TOKEN || true)" ] && set_env EZRA_API_BEARER_TOKEN "$(gen_token)"
  ok "wrote $ENV_FILE"
}

# ============================================================================
main() {
  banner
  detect
  menu
  step "Thanks for installing Ezra."
  say "  Docs: ${B}https://ezra128.vercel.app/docs${R}   ·   Source: ${B}${EZRA_REPO%.git}${R}"
}

# Read interactive answers from the terminal even when the script is piped (curl | bash
# makes the pipe stdin). The redirect must apply to the main *call* — doing it earlier
# would make bash read the rest of the script body from the tty and hang on a blank prompt.
if [ ! -t 0 ] && [ -r /dev/tty ]; then main "$@" </dev/tty; else main "$@"; fi
