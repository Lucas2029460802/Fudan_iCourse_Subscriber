#!/usr/bin/env bash
# Dump summaries from the local (or merged) database and force-push the
# resulting tree to the Overview branch.
set -euo pipefail
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

if [ -f data/remote.db ]; then
  DB=data/remote.db
elif [ -f data/icourse.db ]; then
  DB=data/icourse.db
else
  echo "No database file, skipping Overview publish."
  exit 0
fi

OUT=/tmp/overview_src
rm -rf "$OUT"
python scripts/publish_overview.py --db "$DB" --out "$OUT"

if [ ! -d "$OUT" ]; then
  echo "Overview output missing, skipping."
  exit 0
fi

REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

rm -rf /tmp/overview_deploy
mkdir -p /tmp/overview_deploy
cp -a "$OUT"/. /tmp/overview_deploy/
cd /tmp/overview_deploy

git init -q
git checkout -q -b Overview
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add .
git commit -q -m "docs: update course overviews"
git remote add origin "https://x-access-token:${TOKEN}@github.com/${REPO}.git"

if git fetch --depth=1 origin Overview 2>/dev/null \
   && git rev-parse "origin/Overview^{tree}" >/dev/null 2>&1; then
  if [ "$(git rev-parse "HEAD^{tree}")" = "$(git rev-parse "origin/Overview^{tree}")" ]; then
    echo "Overview tree unchanged, skipping push."
    exit 0
  fi
fi

git push --force origin Overview
echo "Pushed Overview branch."
