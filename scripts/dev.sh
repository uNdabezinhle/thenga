#!/usr/bin/env bash
# Northbound / Reka local helpers
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
PY="$BACKEND/.venv/bin/python"

ensure_venv() {
  if [[ ! -x "$PY" ]]; then
    python3 -m venv "$BACKEND/.venv"
    "$BACKEND/.venv/bin/pip" install -U pip
    "$BACKEND/.venv/bin/pip" install -r "$BACKEND/requirements.txt"
  fi
}

cmd="${1:-help}"
case "$cmd" in
  setup)
    ensure_venv
    (cd "$BACKEND" && "$PY" manage.py migrate --noinput && "$PY" manage.py seed_northbound)
    echo "Ready. Run: ./scripts/dev.sh run"
    ;;
  run)
    ensure_venv
    echo "API + SPA  http://127.0.0.1:8000/"
    (cd "$BACKEND" && "$PY" manage.py runserver 127.0.0.1:8000)
    ;;
  test)
    ensure_venv
    (cd "$BACKEND" && "$PY" manage.py test apps.pricing apps.accounts apps.cart apps.orders apps.payments apps.notifications -v 1)
    ;;
  e2e)
    ensure_venv
    (cd "$BACKEND" && "$PY" scripts_e2e_test.py)
    ;;
  seed)
    ensure_venv
    (cd "$BACKEND" && "$PY" manage.py seed_northbound)
    ;;
  compose)
    (cd "$ROOT" && docker compose up --build)
    ;;
  *)
    cat <<EOF
Northbound dev script
  ./scripts/dev.sh setup|run|test|e2e|seed|compose
EOF
    ;;
esac
