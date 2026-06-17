#!/usr/bin/env bash
# Launch eigent locally per server/README_EN.md: backend via Docker Compose,
# frontend in local mode with .env.development and npm run dev (proxy to backend).
set -euo pipefail

EIGENT_DIR="${EIGENT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$EIGENT_DIR"

echo "==> Backend: copy .env.example to .env if needed"
cd "$EIGENT_DIR/server"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> Backend: start services (Docker Compose)"
docker compose up --build -d
cd "$EIGENT_DIR"

echo "==> Frontend: ensure .env.development (local mode, point to local backend)"
cat > .env.development <<'EOF'
VITE_BASE_URL=/api
VITE_USE_LOCAL_PROXY=true
VITE_PROXY_URL=http://localhost:3001
EOF

echo "==> Frontend: install dependencies"
if [[ -f package-lock.json || -f npm-shrinkwrap.json ]]; then
  npm ci
else
  npm install
fi

echo "==> Frontend: start dev server (API proxied to http://localhost:3001)"
exec npm run dev
