# ---------------------------------------------------------------------------
# Network & Security
# ---------------------------------------------------------------------------

resource "openstack_networking_network_v2" "sof" {
  name           = "${var.instance_name}-net"
  admin_state_up = true
}

resource "openstack_networking_subnet_v2" "sof" {
  name       = "${var.instance_name}-subnet"
  network_id = openstack_networking_network_v2.sof.id
  cidr       = "10.0.0.0/24"
  ip_version = 4
}

resource "openstack_networking_router_v2" "sof" {
  name                = "${var.instance_name}-router"
  admin_state_up      = true
  external_network_id = data.openstack_networking_network_v2.ext_net.id
}

resource "openstack_networking_router_interface_v2" "sof" {
  router_id = openstack_networking_router_v2.sof.id
  subnet_id = openstack_networking_subnet_v2.sof.id
}

data "openstack_networking_network_v2" "ext_net" {
  name = "Ext-Net"
}

resource "openstack_networking_secgroup_v2" "sof" {
  name        = "${var.instance_name}-sg"
  description = "Security group for SOF production"
}

resource "openstack_networking_secgroup_rule_v2" "ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.ssh_cidr
  security_group_id = openstack_networking_secgroup_v2.sof.id
}

resource "openstack_networking_secgroup_rule_v2" "http" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.sof.id
}

resource "openstack_networking_secgroup_rule_v2" "https" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.sof.id
}

resource "openstack_networking_secgroup_rule_v2" "api" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8000
  port_range_max    = 8000
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.sof.id
}

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

resource "openstack_compute_instance_v2" "sof" {
  name            = var.instance_name
  image_name      = var.image
  flavor_name     = var.flavor
  key_pair        = var.ssh_keypair
  security_groups = [openstack_networking_secgroup_v2.sof.name]

  network {
    uuid = openstack_networking_network_v2.sof.id
  }

  user_data = file("${path.module}/user-data.sh")

  lifecycle {
    ignore_changes = [user_data]
  }
}

resource "openstack_networking_floatingip_v2" "sof" {
  pool = data.openstack_networking_network_v2.ext_net.name
}

resource "openstack_compute_floatingip_associate_v2" "sof" {
  floating_ip = openstack_networking_floatingip_v2.sof.address
  instance_id = openstack_compute_instance_v2.sof.id
}

# ---------------------------------------------------------------------------
# Managed PostgreSQL (OVH Cloud Databases)
# ---------------------------------------------------------------------------

resource "ovh_cloud_project_database" "pg" {
  service_name = var.ovh_service_name
  description  = "${var.instance_name}-postgres"
  engine       = "postgresql"
  version      = var.db_pg_version
  plan         = var.db_plan
  nodes {
    region = var.region
  }
  flavor = var.db_flavor
}

resource "ovh_cloud_project_database_postgresql_user" "omop" {
  service_name = var.ovh_service_name
  cluster_id   = ovh_cloud_project_database.pg.id
  name         = "omop"
  password     = random_password.pg.result
}

resource "random_password" "pg" {
  length  = 32
  special = false
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "public_ip" {
  description = "Public IP of the instance"
  value       = openstack_networking_floatingip_v2.sof.address
}

output "ssh_command" {
  description = "SSH command to connect"
  value       = "ssh -i ~/.ssh/${var.ssh_keypair}.key debian@${openstack_networking_floatingip_v2.sof.address}"
}

output "db_host" {
  description = "PostgreSQL managed DB host"
  value       = ovh_cloud_project_database.pg.endpoints[0].domain
}

output "db_password" {
  description = "PostgreSQL user password"
  value       = ovh_cloud_project_database_postgresql_user.omop.password
  sensitive   = true
}

output "api_url" {
  description = "API base URL"
  value       = "http://${openstack_networking_floatingip_v2.sof.address}:8000"
}
