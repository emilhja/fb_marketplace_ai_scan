#!/usr/bin/env bash
#
# install_git_hooks.sh
#
# Installs the repository pre-push helper as .git/hooks/pre-push.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_PATH="$ROOT_DIR/.git/hooks/pre-push"
SOURCE_PATH="$ROOT_DIR/scripts/pre_push_check.sh"

if [ ! -d "$ROOT_DIR/.git/hooks" ]; then
    echo "No .git/hooks directory found. Run this inside a git checkout."
    exit 1
fi

ln -sf ../../scripts/pre_push_check.sh "$HOOK_PATH"
chmod +x "$SOURCE_PATH" "$HOOK_PATH"

echo "Installed pre-push hook:"
echo "  $HOOK_PATH -> ../../scripts/pre_push_check.sh"
echo ""
echo "By default pushes from main are blocked."
echo "Override intentionally with:"
echo "  ALLOW_PUSH_TO_MAIN=1 git push"
