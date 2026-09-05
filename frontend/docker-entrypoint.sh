#!/bin/sh
set -eu

export PORT="${PORT:-80}"

# Compose: http://api:8000
# Render:  https://YOUR-API-SERVICE.onrender.com  (public URL — most reliable)
export API_UPSTREAM="${API_UPSTREAM:-http://api:8000}"

export API_HOST="$(
  printf '%s' "$API_UPSTREAM" | sed -e 's|^[a-zA-Z][a-zA-Z0-9+.-]*://||' -e 's|/.*||'
)"

envsubst '${PORT} ${API_UPSTREAM} ${API_HOST}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
