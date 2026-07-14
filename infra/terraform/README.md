# Terraform — OVH Public Cloud

Infrastructure as Code pour déployer la stack **synthea-to-omop-fhir** sur OVH.

## Architecture

- **Instance** : Debian 12 + Docker + Docker Compose
- **Réseau** : réseau privé + floating IP publique + security group (22, 80, 443, 8000)
- **BDD** : PostgreSQL managé via OVH Cloud Databases
- **Application** : API + Dashboard + HAPI FHIR via `docker-compose.prod.yml`

## Prérequis

1. [OVH Public Cloud](https://www.ovhcloud.com/fr/public-cloud/) activé
2. [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
3. Variables d'environnement OpenStack :
   ```bash
   export OS_AUTH_URL="https://auth.cloud.ovh.net/v3"
   export OS_USERNAME="..."
   export OS_PASSWORD="..."
   export OS_TENANT_NAME="..."
   export OS_REGION_NAME="GRA11"
   ```
4. Clé SSH enregistrée dans OVH (OpenStack keypair)
5. Token OVH API pour Cloud Databases :
   ```bash
   export OVH_APPLICATION_KEY="..."
   export OVH_APPLICATION_SECRET="..."
   export OVH_CONSUMER_KEY="..."
   ```

## Déploiement

```bash
cd infra/terraform

terraform init
terraform plan -var="ssh_keypair=ma-cle-ovh" -var="ovh_service_name=abc123"
terraform apply -var="ssh_keypair=ma-cle-ovh" -var="ovh_service_name=abc123"
```

## Outputs

| Output | Description |
|--------|-------------|
| `public_ip` | IP publique de l'instance |
| `ssh_command` | Commande SSH pour se connecter |
| `db_host` | Host PostgreSQL managé |
| `api_url` | URL de l'API |

## Post-déploiement

Se connecter en SSH et vérifier :
```bash
ssh -i ~/.ssh/ma-cle-ovh.key debian@<public_ip>
docker compose -f /opt/synthea-to-omop-fhir/docker-compose.prod.yml ps
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

## Destruction

```bash
terraform destroy
```
