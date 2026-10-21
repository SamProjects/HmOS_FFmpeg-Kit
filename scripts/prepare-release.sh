#!/usr/bin/env bash
# Pin the source tag before a long build. GITHUB_TOKEN cannot create a new
# release tag for a stale workflow revision after main's workflows change.
set -euo pipefail
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_SHA:?}" "${GITHUB_ENV:?}"
notes=docs/RELEASE-NOTES.md
version=$(python3 -c 'import json; print(json.load(open("config/project.json"))["version"])')
tag="v${version}-ci.${GITHUB_RUN_NUMBER}"
if [[ "${REF_TYPE:-}" == tag ]]; then tag="$REF_NAME"; fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if ! gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$tag" > "$tmp/ref.json" 2> "$tmp/error"; then
  grep -q 'HTTP 404' "$tmp/error" || { cat "$tmp/error"; exit 1; }
  gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" \
    -f ref="refs/tags/$tag" -f sha="$GITHUB_SHA" > /dev/null
  gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$tag" > "$tmp/ref.json"
fi
type=$(jq -r .object.type "$tmp/ref.json")
sha=$(jq -r .object.sha "$tmp/ref.json")
for depth in 1 2 3 4 5; do
  [[ "$type" == tag ]] || break
  gh api "repos/$GITHUB_REPOSITORY/git/tags/$sha" > "$tmp/ref.json"
  type=$(jq -r .object.type "$tmp/ref.json")
  sha=$(jq -r .object.sha "$tmp/ref.json")
done
[[ "$type" == commit && "$sha" == "$GITHUB_SHA" ]] || {
  echo '发布标签与构建源码不一致，停止构建。'; exit 1;
}
if gh release view "$tag" --repo "$GITHUB_REPOSITORY" --json isDraft,targetCommitish > "$tmp/release.json" 2> "$tmp/error"; then
  [[ $(jq -r .isDraft "$tmp/release.json") == true ]] || {
    echo '该版本已经发布，不覆盖已有发布包。'; exit 1;
  }
else
  grep -qiE 'not found|HTTP 404' "$tmp/error" || { cat "$tmp/error"; exit 1; }
  gh release create "$tag" --repo "$GITHUB_REPOSITORY" --verify-tag --draft \
    --target "$GITHUB_SHA" --prerelease --title "鸿蒙 FFmpeg $tag（构建中草稿）" \
    --notes-file "$notes"
fi
echo "RELEASE_TAG=$tag" >> "$GITHUB_ENV"
echo "发布权限已检查，标签已固定到本次构建源码：$tag $GITHUB_SHA"
