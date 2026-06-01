# Reusable tools image: node + jose (pinned to the vendored docs/jose version)
# + openssl. Keeps everything off the host per the "no local installs" rule.
#   docker build -t ezra/jose-tools scripts/gcp_auth
FROM node:22-bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN npm init -y >/dev/null 2>&1 && npm install --silent jose@6.2.3
COPY gen_keypair.mjs mint_token.mjs ./
ENTRYPOINT ["node"]
