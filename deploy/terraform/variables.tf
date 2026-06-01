variable "project_id" {
  type        = string
  description = "GCP project id."
  default     = "ezra-498021"
}

variable "project_number" {
  type        = string
  description = "GCP project number (used in WIF member strings)."
  default     = "554390343398"
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "zone" {
  type    = string
  default = "us-east1-c"
}

variable "ar_repo" {
  type        = string
  description = "Artifact Registry Docker repository id."
  default     = "ezra"
}

variable "runtime_gsa_email" {
  type        = string
  description = "Existing Google service account the workload runs as (via Workload Identity)."
  default     = "ezra-ai-developer@ezra-498021.iam.gserviceaccount.com"
}

variable "k8s_namespace" {
  type    = string
  default = "ezra"
}

variable "k8s_service_account" {
  type    = string
  default = "ezra-api"
}

variable "secret_ids" {
  type        = list(string)
  description = "Secret Manager secret ids the workload reads (values pushed separately)."
  default     = ["ezra-mongodb-uri", "ezra-llm-api-key", "ezra-api-bearer-token"]
}

# --- GKE cluster (held off by default — set true when ready to provision) --- #
variable "create_cluster" {
  type        = bool
  description = "Create the GKE cluster + node pool. Costs credits; keep false until ready."
  default     = false
}

variable "cluster_name" {
  type    = string
  default = "ezra"
}

variable "node_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "node_count" {
  type    = number
  default = 1
}
