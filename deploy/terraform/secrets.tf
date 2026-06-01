# Secret Manager secrets (the metadata/containers). Values are NOT managed here —
# they're pushed with deploy/scripts/bootstrap_secrets.sh so plaintext never
# lands in Terraform state or git. At runtime the workload reads them via the
# GKE Secret Manager add-on (SecretProviderClass) under Workload Identity.

resource "google_secret_manager_secret" "ezra" {
  for_each = toset(var.secret_ids)

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}
