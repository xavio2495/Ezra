# GKE cluster — gated by `create_cluster` (default false; costs credits).
# Flip create_cluster=true (terraform.tfvars) when ready to provision.
#
# Zonal single-node cluster with Workload Identity + the Secret Manager add-on
# (provides the Secret Manager CSI driver the K8s SecretProviderClass uses).

resource "google_container_cluster" "ezra" {
  count = var.create_cluster ? 1 : 0

  name     = var.cluster_name
  project  = var.project_id
  location = var.zone

  # Start with a default pool then replace it with our managed pool below.
  initial_node_count       = 1
  remove_default_node_pool = true
  deletion_protection      = false

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  secret_manager_config {
    enabled = true
  }

  depends_on = [google_project_service.enabled]
}

resource "google_container_node_pool" "primary" {
  count = var.create_cluster ? 1 : 0

  name     = "primary"
  project  = var.project_id
  location = var.zone
  cluster  = google_container_cluster.ezra[0].name

  node_count = var.node_count

  node_config {
    machine_type = var.node_machine_type
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
}
