#!/usr/bin/env bash
# Deploy Brain + web UI to ai.steamocloud.com (EC2).
set -euo pipefail

EIGENT_DIR="${EIGENT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
SSH_KEY="${SSH_KEY:-$HOME/certs/key_database.pem}"
SSH_HOST="${SSH_HOST:-ubuntu@ai.steamocloud.com}"
DOMAIN="${DOMAIN:-ai.steamocloud.com}"

echo "==> Sync deploy configs to EC2"
scp -i "$SSH_KEY" \
  "$EIGENT_DIR/deploy/eigent-brain.service" \
  "$EIGENT_DIR/deploy/nginx-${DOMAIN}.conf" \
  "$SSH_HOST:/tmp/"

echo "==> Install Brain dependencies and systemd service"
ssh -i "$SSH_KEY" "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

cd /opt/eigent/backend
uv python install 3.11
uv sync --no-dev

mkdir -p /home/ubuntu/.eigent/workspace

sudo mv /tmp/eigent-brain.service /etc/systemd/system/eigent-brain.service
sudo systemctl daemon-reload
sudo systemctl enable eigent-brain
sudo systemctl restart eigent-brain

echo "==> Waiting for Brain health"
for i in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:5001/health >/dev/null 2>&1; then
    echo "Brain healthy"
    curl -fsS http://127.0.0.1:5001/health
    break
  fi
  if [ "$i" -eq 90 ]; then
    echo "Brain failed to start"
    sudo journalctl -u eigent-brain -n 80 --no-pager
    exit 1
  fi
  sleep 3
done

sudo mv /tmp/nginx-ai.steamocloud.com.conf /etc/nginx/conf.d/eigent.conf
sudo nginx -t
sudo systemctl reload nginx
REMOTE

echo "==> Deploy web UI (dist-web)"
ssh -i "$SSH_KEY" "$SSH_HOST" "sudo mkdir -p /var/www/eigent-web && sudo chown ubuntu:ubuntu /var/www/eigent-web"
rsync -avz --delete -e "ssh -i $SSH_KEY" \
  "$EIGENT_DIR/dist-web/" \
  "$SSH_HOST:/var/www/eigent-web/"

echo "==> Done: https://${DOMAIN}/"
echo "    Brain health: https://${DOMAIN}/health"
echo "    Server API:   https://${DOMAIN}/api/docs"
