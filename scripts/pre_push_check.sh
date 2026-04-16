#!/usr/bin/env bash
#
# pre_push_check.sh
#
# A comprehensive manual check of all safety, quality, and security gates
# before pushing to GitHub.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env"
    set +a
fi

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "🚀 Starting full project verification..."

# 0a. Branch guard
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "main" ] && [ "${ALLOW_PUSH_TO_MAIN:-0}" != "1" ]; then
    echo -e "${RED}❌ Refusing to push directly to main.${NC}"
    warn "Set ALLOW_PUSH_TO_MAIN=1 if this is intentional."
    exit 1
elif [ "$CURRENT_BRANCH" = "main" ]; then
    warn "Pushing directly to main because ALLOW_PUSH_TO_MAIN=1 is set."
fi

# 0b. Check for accidentally tracked secret files
echo -e "\n🔒 Checking for accidentally tracked secret files..."
TRACKED_SECRETS=$(git ls-files .env personal.toml 2>/dev/null)
if [ -n "$TRACKED_SECRETS" ]; then
    echo -e "${RED}❌ Secret files tracked by git: $TRACKED_SECRETS${NC}"
    exit 1
fi

# 1. Pre-commit hooks
echo -e "\n🔍 Running blocking pre-commit hooks (Secrets, Repo Safety)..."
if ! pre-commit run gitleaks --all-files; then
    echo -e "${RED}❌ Secret scanning failed.${NC}"
    exit 1
fi
if ! pre-commit run check-yaml --all-files; then
    echo -e "${RED}❌ YAML validation failed.${NC}"
    exit 1
fi
if ! pre-commit run check-toml --all-files; then
    echo -e "${RED}❌ TOML validation failed.${NC}"
    exit 1
fi
if ! pre-commit run check-added-large-files --all-files; then
    echo -e "${RED}❌ Large file check failed.${NC}"
    exit 1
fi
if ! pre-commit run check-repo-hygiene --all-files; then
    echo -e "${RED}❌ Repo hygiene check failed.${NC}"
    exit 1
fi

echo -e "\n🧹 Running non-blocking formatting hooks..."
if ! pre-commit run trailing-whitespace --all-files; then
    warn "trailing-whitespace reported fixes or issues, but push is still allowed."
fi
if ! pre-commit run end-of-file-fixer --all-files; then
    warn "end-of-file-fixer reported fixes or issues, but push is still allowed."
fi

# 2. Dependency Audit
echo -e "\n🛡️  Running pip-audit..."
# CVE-2025-69872: diskcache 5.6.3 — known issue, no fix available upstream yet
PIP_AUDIT_CMD=(pip-audit)
if [ -x ".venv/bin/python" ]; then
    PIP_AUDIT_CMD=(.venv/bin/python -m pip_audit)
fi

echo "Using pip-audit command: ${PIP_AUDIT_CMD[*]}"

if ! "${PIP_AUDIT_CMD[@]}" --ignore-vuln CVE-2025-69872; then
    echo -e "${RED}❌ pip-audit found unignored vulnerabilities.${NC}"
    exit 1
fi

# 3. Python Tests
echo -e "\n🧪 Running Pytest..."
if ! pytest; then
    echo -e "${RED}❌ Tests failed.${NC}"
    exit 1
fi

# 4. Frontend Checks
echo -e "\n💻 Verifying Frontend..."
pushd frontend >/dev/null
if ! npm run lint; then
    warn "Frontend lint reported issues, but push is still allowed."
fi
if ! npm run build; then
    echo -e "${RED}❌ Frontend build failed.${NC}"
    exit 1
fi
echo -e "\n🔐 Running npm audit..."
if ! npm audit --audit-level=high; then
    echo -e "${RED}❌ npm audit found high/critical vulnerabilities.${NC}"
    exit 1
fi
popd >/dev/null

echo -e "\n${GREEN}✨ ALL CHECKS PASSED! Ready to push. ✨${NC}"
