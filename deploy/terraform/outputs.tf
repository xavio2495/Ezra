output "artifact_registry_repo" {
  description = "Docker image prefix to tag/push against."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo}"
}

output "runtime_gsa_email" {
  value = var.runtime_gsa_email
}

output "secret_ids" {
  value = var.secret_ids
}

output "workload_identity_member" {
  description = "The KSA principal bound to the runtime GSA."
  value       = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/${var.k8s_service_account}]"
}

output "cluster_name" {
  value = var.create_cluster ? google_container_cluster.ezra[0].name : "(not created — set create_cluster=true)"
}

output "github_wif_provider" {
  description = "Pass to google-github-actions/auth as workload_identity_provider."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_sa_email" {
  description = "Pass to google-github-actions/auth as service_account."
  value       = google_service_account.deployer.email
}
