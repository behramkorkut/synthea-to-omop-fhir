# Sovereign deployment (OVH / SecNumCloud-ready)

French health data must be hosted by an **HDS-certified** provider, and the most
sensitive public platforms are moving to **SecNumCloud** (sovereign, outside the
US Cloud Act). This project is **cloud-agnostic** (Python, DuckDB/PostgreSQL,
Docker), so it deploys on a sovereign cloud without code changes.

## Target

A small **OVHcloud** VPS (or Scaleway) running Docker. The stack (cohort API +
dashboard + optional HAPI FHIR) starts with `docker compose up`.

## Steps (summary)

1. **Provision** a VPS (Ubuntu LTS) on OVH/Scaleway.
2. **Harden the host**: SSH keys only (`PasswordAuthentication no`), `ufw`
   (allow 22/80/443 only), `fail2ban`, unattended-upgrades, a swap file.
3. **Install Docker** + the Compose plugin.
4. **Deploy**: clone the repo, build the OMOP warehouse (or mount it), then
   `docker compose up -d`.
5. **Reverse proxy + TLS**: put **nginx** in front, terminate **TLS** with
   Let's Encrypt; expose only the API/dashboard, keep containers bound to
   loopback.
6. **Backups & monitoring**: snapshot the `data/` volume; basic uptime/logs.

> This mirrors the production deployment of my `readmission-risk-ml` project,
> already live on an OVHcloud VPS (SSH hardening, nginx + TLS, Docker).

## Why sovereign matters here

For public health-research data in France, **SecNumCloud** excludes Azure/AWS/GCP
(US extraterritorial law). A sovereign target (OVH/Scaleway) is therefore not a
detail but a **compliance requirement** — and a strong talking point: the
Plateforme des Données de Santé is itself migrating off Azure to a sovereign
cloud. Being cloud-agnostic + sovereign-ready is a deliberate design choice.

## Production hardening (beyond this demo)

Real patient data would additionally require: HDS-certified hosting, a
pseudonymisation service with key management, RBAC + audit logging to a SIEM,
a declared RGPD legal basis and CNIL reference methodology (MR-004), and DPO
oversight (see [`governance_rgpd_hds.md`](governance_rgpd_hds.md)).
