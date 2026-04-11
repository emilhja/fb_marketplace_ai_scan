#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

source "$SCRIPT_DIR/.venv/bin/activate"

python3 "$SCRIPT_DIR/scripts/apply_ai_marketplace_monitor_patches.py"

# Esc to skip the Facebook login wait uses pynput (global key listener). Under Wayland
# or some terminals it may not fire; the shell may only echo ^[. Then either wait the
# full login_wait_time or lower it in ~/.ai-marketplace-monitor/config.toml .
if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    echo "ai-marketplace-monitor: Wayland detected — Esc may not end the login wait; use a shorter login_wait_time if needed." >&2
fi

ai-marketplace-monitor "$@"
