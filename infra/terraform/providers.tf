terraform {
  required_version = ">= 1.5"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = ">= 1.53"
    }
    ovh = {
      source  = "ovh/ovh"
      version = ">= 0.36"
    }
  }
}

# OVH Public Cloud uses standard OpenStack endpoints.
# Set these via environment variables:
#   export OS_AUTH_URL="https://auth.cloud.ovh.net/v3"
#   export OS_USERNAME="..."
#   export OS_PASSWORD="..."
#   export OS_TENANT_NAME="..."
#   export OS_REGION_NAME="..."
provider "openstack" {}

provider "ovh" {}
