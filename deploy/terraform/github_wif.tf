# Keyless CD auth for GitHub Actions — restricted to the `release` branch only.
#
# A WIF pool + OIDC provider trusts GitHub's token issuer, but the attribute
# condition only mints credentials for THIS repo on refs/heads/release. So a
# workflow on `main` (or any other branch/fork) cannot obtain GCP access —
# GKE is fed only from `release`. The `ezra-deployer` SA (AR writer + GKE
# developer) is what the release workflow impersonates. No SA keys.

variable "github_repo" {
  type        = string
  description = "owner/repo that may deploy."
  default     = "xavio2495/Ezra"
}

variable "github_deploy_branch" {
  type        = string
  description = "The only branch allowed to deploy."
  default     = "release"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Only our repo's release branch may exchange a token.
  attribute_condition = "assertion.repository == '${var.github_repo}' && assertion.ref == 'refs/heads/${var.github_deploy_branch}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "ezra-deployer"
  display_name = "Ezra GitHub Actions deployer (release branch)"
}

resource "google_project_iam_member" "deployer_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_gke_developer" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Let the release-branch workflow impersonate the deployer SA (branch is further
# constrained by the provider's attribute_condition above).
resource "google_service_account_iam_member" "deployer_workload_identity" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
