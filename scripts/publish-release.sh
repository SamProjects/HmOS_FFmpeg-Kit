#!/usr/bin/env bash
set -euo pipefail
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${RELEASE_TAG:?}"
notes=docs/RELEASE-NOTES.md
label='预发布版'
if [[ "${HMOS_COMMAND_TEST:-0}" == 1 ]]; then
  notes=docs/COMMAND-TEST.zh-CN.md
  label='命令执行实验版'
fi
# Verify the actual tag commit; target_commitish metadata is not authoritative
# when the release was created for a tag that already existed.
git fetch --no-tags origin "refs/tags/$RELEASE_TAG"
[[ $(git rev-parse 'FETCH_HEAD^{commit}') == "$GITHUB_SHA" ]] || {
  echo '发布标签已变化，与构建提交不一致。'; exit 1;
}
python3 scripts/check-release.py dist/assets
if [[ "${HMOS_HAR_ONLY:-0}" != 1 ]]; then
  (cd dist/assets; sha256sum *.har *.tar.gz *.json > SHA256SUMS)
fi
# Only a draft prepared for this exact source may receive files.
draft=$(gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --json isDraft --jq .isDraft)
[[ "$draft" == true ]] || { echo '拒绝覆盖已发布版本。'; exit 1; }
uploaded=false
for attempt in 1 2 3; do
  if gh release upload "$RELEASE_TAG" dist/assets/* --clobber --repo "$GITHUB_REPOSITORY"; then
    uploaded=true; break
  fi
  echo "第 $attempt 次上传未完成。"
  if [[ "$attempt" != 3 ]]; then sleep 10; fi
done
[[ "$uploaded" == true ]] || { echo '上传失败，保留草稿供排查，不公开不完整发布。'; exit 1; }
release_id=$(gh release view "$RELEASE_TAG" --repo "$GITHUB_REPOSITORY" --json databaseId --jq .databaseId)
remote=$(mktemp)
trap 'rm -f "$remote"' EXIT
gh api "repos/$GITHUB_REPOSITORY/releases/$release_id" > "$remote"
python3 scripts/check-upload.py dist/assets "$remote"
for attempt in 1 2 3; do
  if gh release edit "$RELEASE_TAG" --draft=false --prerelease \
    --title "鸿蒙 FFmpeg $RELEASE_TAG（$label）" \
    --notes-file "$notes" --repo "$GITHUB_REPOSITORY"; then
    echo '所有发布文件已核对并公开，标题和说明均为中文。'; exit 0
  fi
  if [[ "$attempt" != 3 ]]; then sleep 10; fi
done
echo '发布确认失败；文件已经上传，请核对草稿状态。'; exit 1
