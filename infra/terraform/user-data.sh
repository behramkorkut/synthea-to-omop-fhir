#!/usr/bin/env bash
# cloud-init / user-data for OVH instance boot
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# --- Docker & Compose ---
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# --- Clone repo (public) ---
mkdir -p /opt
if [ ! -d /opt/synthea-to-omop-fhir ]; then
  git clone https://github.com/behramko/synthea-to-omop-fhir.git /opt/synthea-to-omop-fhir
fi

cd /opt/synthea-to-omop-fhir

# --- Env file ---
cat > .env.prod << 'EOF'
DB_ENGINE=postgres
POSTGRES_DSN=postgresql://omop:${db_password}@${db_host}:5432/omop
API_KEY=${api_key}
RATE_LIMIT_PER_MINUTE=60
LOG_FORMAT=json
LOG_LEVEL=INFO
EOF

# --- Run prod stack ---
docker compose -f docker-compose.prod.yml up --build -d

# --- Basic health check ---
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null; then
    echo "API is up"
    break
  fi
  sleep 5
done
