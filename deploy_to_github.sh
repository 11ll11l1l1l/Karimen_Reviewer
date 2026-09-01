#!/usr/bin/env bash
set -euo pipefail
REPO_URL="${1:-https://github.com/11ll11l1l1l/Karimen_Reviewer.git}"
BRANCH="${2:-main}"
SOURCE="$(cd "$(dirname "$0")" && pwd)"
WORK="${TMPDIR:-/tmp}/Karimen_Reviewer_v53_deploy"
rm -rf "$WORK"
git clone --branch "$BRANCH" "$REPO_URL" "$WORK"
rsync -a --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.v51bak' --exclude='deploy_to_github.ps1' --exclude='deploy_to_github.sh' "$SOURCE/" "$WORK/"
cd "$WORK"
git add -A
if git diff --cached --quiet; then
  echo "No Git changes detected. Repository already matches this package."
  exit 0
fi
git commit -m "Upgrade Japan Driving License Exam Reviewer to v5.3"
git push origin "$BRANCH"
echo "v5.3 pushed successfully to $BRANCH."
echo "Next: check GitHub Actions / Streamlit deployment, then run supabase_setup.sql once if player_profiles does not exist."
