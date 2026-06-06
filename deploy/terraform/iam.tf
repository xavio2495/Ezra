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

# The ingest job (running as the runtime GSA via WI) runs BigQuery jobs.
# bigquery.jobUser lets it run query/load jobs billed to this project.
resource "google_project_iam_member" "runtime_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.runtime_gsa_email}"
}

# Writing the F1 results table needs table create/write — granted at the DATASET
# level (least privilege; not project-wide). jobUser runs the job, this lets it
# create/replace + load the table inside formula_1.
resource "google_bigquery_dataset_iam_member" "runtime_dataset_editor" {
  project    = var.project_id
  dataset_id = "formula_1"
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${var.runtime_gsa_email}"
}

# The GKE node service account must be able to PULL the API image from Artifact
# Registry. cloud-platform oauth scope alone is NOT sufficient — the SA needs the
# reader IAM role, or pods ImagePullBackOff with 403.
resource "google_artifact_registry_repository_iam_member" "node_puller" {
  project    = var.project_id
  location   = google_artifact_registry_repository.ezra.location
  repository = google_artifact_registry_repository.ezra.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.project_number}-compute@developer.gserviceaccount.com"
}
