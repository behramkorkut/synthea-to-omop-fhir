variable "region" {
  description = "OVH region (e.g. GRA11, SBG5, BHS5)"
  type        = string
  default     = "GRA11"
}

variable "instance_name" {
  description = "Name prefix for the compute instance"
  type        = string
  default     = "sof-prod"
}

variable "flavor" {
  description = "OVH instance flavor (e.g. b2-7, c2-15)"
  type        = string
  default     = "b2-7"
}

variable "image" {
  description = "OS image name (e.g. Debian 12, Ubuntu 22.04)"
  type        = string
  default     = "Debian 12"
}

variable "ssh_keypair" {
  description = "Name of an existing OpenStack keypair"
  type        = string
}

variable "ssh_cidr" {
  description = "CIDR allowed for SSH inbound"
  type        = string
  default     = "0.0.0.0/0"
}

variable "api_domain" {
  description = "Domain name pointing to the instance (for nginx/letsencrypt)"
  type        = string
  default     = ""
}

variable "db_pg_version" {
  description = "PostgreSQL version for OVH managed DB"
  type        = string
  default     = "16"
}

variable "db_plan" {
  description = "OVH Cloud DB plan (e.g. essential, business, enterprise)"
  type        = string
  default     = "essential"
}

variable "ovh_service_name" {
  description = "OVH service name (project ID) for Cloud Databases"
  type        = string
}

variable "db_flavor" {
  description = "OVH Cloud DB flavor (e.g. db1-7)"
  type        = string
  default     = "db1-7"
}
