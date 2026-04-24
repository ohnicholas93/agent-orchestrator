#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$SCRIPT_DIR/skills"
TARGET_ROOT="${HOME}/.agents/skills"
MODE="${1:-install}"

usage() {
  printf 'usage: ./installer.sh [install|uninstall]\n' >&2
  exit 1
}

case "$MODE" in
  install|uninstall)
    ;;
  *)
    usage
    ;;
esac

mkdir -p "$TARGET_ROOT"

cleanup_renamed_skill_link() {
  old_name="$1"
  new_name="$2"
  old_path="$TARGET_ROOT/$old_name"
  new_target="$SOURCE_ROOT/$new_name"

  if [[ ! -L "$old_path" ]]; then
    return
  fi

  current_target="$(readlink "$old_path")"
  case "$current_target" in
    "$SOURCE_ROOT/$old_name"|"$new_target")
      rm "$old_path"
      printf 'removed legacy link %s\n' "$old_path"
      ;;
    *)
      ;;
  esac
}

# Handle known skill renames so upgrades do not leave stale links behind.
cleanup_renamed_skill_link "privileged-researcher" "privileged-automation"
cleanup_renamed_skill_link "unprivileged-researcher" "unprivileged-automation"

found=0
for skill_dir in "$SOURCE_ROOT"/*; do
  if [[ ! -d "$skill_dir" || ! -f "$skill_dir/SKILL.md" ]]; then
    continue
  fi

  found=1
  skill_name="$(basename "$skill_dir")"
  target_path="$TARGET_ROOT/$skill_name"

  if [[ "$MODE" == "install" ]]; then
    if [[ -L "$target_path" ]]; then
      current_target="$(readlink "$target_path")"
      if [[ "$current_target" == "$skill_dir" ]]; then
        printf 'unchanged %s -> %s\n' "$target_path" "$skill_dir"
        continue
      fi
    elif [[ -e "$target_path" ]]; then
      printf 'error: %s exists and is not a matching symlink\n' "$target_path" >&2
      exit 1
    fi

    ln -sfn "$skill_dir" "$target_path"
    printf 'linked %s -> %s\n' "$target_path" "$skill_dir"
    continue
  fi

  if [[ -L "$target_path" ]]; then
    current_target="$(readlink "$target_path")"
    if [[ "$current_target" == "$skill_dir" ]]; then
      rm "$target_path"
      printf 'removed %s\n' "$target_path"
      continue
    fi
  fi

  printf 'skipped %s\n' "$target_path"
done

if [[ "$found" -eq 0 ]]; then
  printf 'error: no skills found under %s\n' "$SOURCE_ROOT" >&2
  exit 1
fi
