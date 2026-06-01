# Workload Identity + secret access for the runtime service account.
#
# The workload runs as `runtime_gsa_email` (an existing GSA). Two bindings:
#   1. the GKE Kubernetes SA (namespace/name) may impersonate that GSA, and
#   2. that GSA may read each Ezra secret.
# No service-account keys anywhere — this is the keyless WIF path.

# Bind the GKE KSA -> GSA (Workload Identity).
resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.runtime_gsa_email}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.k8s_service_account}]"
}

# Let the GSA read each secret.
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each = google_secret_manager_secret.ezra

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.runtime_gsa_email}"
}
