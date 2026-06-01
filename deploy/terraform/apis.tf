locals {
  required_apis = [
    "artifactregistry.googleapis.com",
    "container.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "bigquery.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.required_apis)

  project = var.project_id
  service = each.value

  # Don't tear APIs down on `terraform destroy` — other things may depend on them.
  disable_on_destroy = false
}
