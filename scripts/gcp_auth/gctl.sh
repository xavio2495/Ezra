#!/usr/bin/env bash
# Run gcloud / kubectl / curl against GCP as the ezra-ai-developer service
# account, using a short-lived token minted by jose. Nothing installed locally:
# jose runs in the `ezra/jose-tools` image, gcloud in `google/cloud-sdk`.
#
#   scripts/gcp_auth/gctl.sh gcloud projects describe ezra-498021
#   scripts/gcp_auth/gctl.sh kubectl get pods
#   scripts/gcp_auth/gctl.sh token            # just print an access token
#
# Requires secrets/gcp/private_key.pem and GCP_SA_KEY_ID (from .env / the
# uploaded key). Build the tools image first: docker build -t ezra/jose-tools scripts/gcp_auth
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS="$ROOT/secrets/gcp"

# Load GCP_* and EZRA_GCP_* from .env without exporting other secrets.
if [[ -f "$ROOT/.env" ]]; then
	set -a
	# shellcheck disable=SC1090
	source <(grep -E '^(EZRA_GCP_|GCP_)' "$ROOT/.env" | sed 's/\r$//')
	set +a
fi

SA_EMAIL="${GCP_SA_EMAIL:-${EZRA_GCP_SERVICE_ACCOUNT_EMAIL:-}}"
KEY_ID="${GCP_SA_KEY_ID:-${EZRA_GCP_SA_KEY_ID:-}}"
PROJECT="${EZRA_GCP_PROJECT_ID:-ezra-498021}"

if [[ -z "$SA_EMAIL" || -z "$KEY_ID" ]]; then
	echo "error: set EZRA_GCP_SERVICE_ACCOUNT_EMAIL and EZRA_GCP_SA_KEY_ID in .env" >&2
	exit 2
fi

mint_token() {
	docker run --rm \
		-v "$SECRETS:/keys:ro" \
		-e GCP_PRIVATE_KEY_PATH=/keys/private_key.pem \
		-e GCP_SA_EMAIL="$SA_EMAIL" \
		-e GCP_SA_KEY_ID="$KEY_ID" \
		ezra/jose-tools mint_token.mjs
}

cmd="${1:-}"
case "$cmd" in
	token)
		mint_token
		echo
		;;
	gcloud | kubectl | gsutil | bq)
		TOKEN="$(mint_token)"
		shift
		docker run --rm \
			-e CLOUDSDK_AUTH_ACCESS_TOKEN="$TOKEN" \
			-e CLOUDSDK_CORE_PROJECT="$PROJECT" \
			google/cloud-sdk:slim "$cmd" "$@"
		;;
	*)
		echo "usage: gctl.sh {token|gcloud|kubectl|gsutil|bq} [args...]" >&2
		exit 1
		;;
esac
