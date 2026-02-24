#!/bin/sh
set -eu

out="/usr/share/nginx/html/env.js"
clerk_url="${VITE_CLERK_PROXY_URL:-}"
clerk_key="${VITE_CLERK_PUBLISHABLE_KEY:-}"
hide_server_models="${VITE_HIDE_SERVER_MODELS:-false}"
base_url="${VITE_BASE_URL:-}"
edition="${VITE_EDITION:-community}"
admin_emails="${VITE_ADMIN_EMAILS:-}"

escaped_clerk="$(printf '%s' "$clerk_url" | sed 's/\\/\\\\/g; s/"/\\"/g')"
escaped_key="$(printf '%s' "$clerk_key" | sed 's/\\/\\\\/g; s/"/\\"/g')"
escaped_hide="$(printf '%s' "$hide_server_models" | sed 's/\\/\\\\/g; s/"/\\"/g')"
escaped_base_url="$(printf '%s' "$base_url" | sed 's/\\/\\\\/g; s/"/\\"/g')"
escaped_edition="$(printf '%s' "$edition" | sed 's/\\/\\\\/g; s/"/\\"/g')"
escaped_admin_emails="$(printf '%s' "$admin_emails" | sed 's/\\/\\\\/g; s/"/\\"/g')"

cat > "$out" <<EOF
window.__ENV = window.__ENV || {};
window.__ENV.VITE_CLERK_PROXY_URL = "$escaped_clerk";
window.__ENV.VITE_CLERK_PUBLISHABLE_KEY = "$escaped_key";
window.__ENV.VITE_HIDE_SERVER_MODELS = "$escaped_hide";
window.__ENV.VITE_BASE_URL = "$escaped_base_url";
window.__ENV.VITE_EDITION = "$escaped_edition";
window.__ENV.VITE_ADMIN_EMAILS = "$escaped_admin_emails";
EOF
