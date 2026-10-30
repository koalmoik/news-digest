#!/bin/bash
# Holt den neuesten Digest von GitHub in den Cache, den die GNOME-Erweiterung liest.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/news-digest"
mkdir -p "$CACHE"
git -C "$DIR" fetch --quiet origin

# Die Routine pusht nach main oder (falls gesperrt) nach claude/digest – der neuere gewinnt
best='' best_time=0
for ref in origin/main origin/claude/digest; do
    git -C "$DIR" cat-file -e "$ref:latest.json" 2>/dev/null || continue
    t=$(git -C "$DIR" log -1 --format=%ct "$ref" -- latest.json)
    if (( t > best_time )); then best=$ref best_time=$t; fi
done
[[ -n $best ]] || exit 0

echo "${best#origin/}" > "$CACHE/branch"
git -C "$DIR" show "$best:latest.json" > "$CACHE/latest.json.tmp"
if cmp -s "$CACHE/latest.json.tmp" "$CACHE/latest.json"; then
    rm "$CACHE/latest.json.tmp"
else
    mv "$CACHE/latest.json.tmp" "$CACHE/latest.json"
fi
