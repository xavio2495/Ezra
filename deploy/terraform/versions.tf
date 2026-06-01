terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Local state by default (gitignored). For shared/CI use, switch to a GCS
  # backend — see deploy/README.md.
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
  # Auth is keyless: set GOOGLE_OAUTH_ACCESS_TOKEN from
  #   gcloud auth print-access-token
  # (no service-account JSON key — SA-key creation is org-blocked here).
}
