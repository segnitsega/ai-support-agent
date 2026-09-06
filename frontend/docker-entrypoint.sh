#!/bin/sh
set -eu

# Browser calls the API directly (CORS is enabled on FastAPI).
# Local Compose: http://127.0.0.1:8000
# Render:        https://YOUR-API.onrender.com
API_BASE="${VITE_API_URL:-}"
API_BASE="${API_BASE%/}"

cat > /app/dist/config.js <<EOF
window.__API_BASE__ = "${API_BASE}";
EOF

# -s: SPA fallback to index.html for /admin, /dashboard, …
exec serve -s dist -l "tcp://0.0.0.0:${PORT:-3000}"
