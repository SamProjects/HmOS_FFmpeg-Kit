#!/usr/bin/env bash
# User policy: no retained Actions artifacts, even after failures.
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
: "${GH_TOKEN:?}"
artifact_ids=$(gh api --paginate "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=100" --jq '.artifacts[].id')
while read -r id; do
  [[ -n "$id" ]] || continue
  if ! response=$(gh api --method DELETE "repos/$GITHUB_REPOSITORY/actions/artifacts/$id" 2>&1); then
    [[ "$response" == *"(HTTP 404)"* ]] || { echo "$response"; exit 1; }
  fi
  echo "Deleted artifact $id"
done <<< "$artifact_ids"
# Only caches created by this project's earlier build workflow are removed.
cache_ids=$(gh api --paginate "repos/$GITHUB_REPOSITORY/actions/caches?per_page=100" --jq '.actions_caches[] | select(.key | startswith("hmos-ccache-")) | .id')
while read -r id; do
  [[ -n "$id" ]] || continue
  if ! response=$(gh api --method DELETE "repos/$GITHUB_REPOSITORY/actions/caches/$id" 2>&1); then
    [[ "$response" == *"(HTTP 404)"* ]] || { echo "$response"; exit 1; }
  fi
  echo "Deleted former build cache $id"
done <<< "$cache_ids"
remaining=$(gh api "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=1" --jq .total_count)
[[ "$remaining" == 0 ]] || { echo "Unexpected remaining artifacts: $remaining"; exit 1; }
echo 'Actions artifacts remaining: 0; no persistent build cache is created.'
