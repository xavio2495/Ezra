resource "google_artifact_registry_repository" "ezra" {
  project       = var.project_id
  location      = var.region
  repository_id = var.ar_repo
  format        = "DOCKER"
  description   = "Ezra Core container images"

  depends_on = [google_project_service.enabled]
}
