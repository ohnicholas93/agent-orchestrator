#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$SCRIPT_DIR/skills"
TARGET_ROOT="${HOME}/.agents/skills"
BIN_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${BIN_DIR}/codex-orchestrator"
BASHRC_PATH="${HOME}/.bashrc"
PATH_BLOCK_START="# >>> codex-orchestrator managed PATH block (may be retained if ~/.local/bin is in use) >>>"
PATH_BLOCK_END="# <<< codex-orchestrator managed PATH block <<<"
MODE="${1:-install}"
MANAGED_WRAPPER_CONTENT='#!/usr/bin/env bash
exec python "$HOME/.agents/skills/codex-orchestrator/scripts/orchestrator.py" "$@"'

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

ensure_path_block() {
  mkdir -p "$(dirname "$BASHRC_PATH")"
  touch "$BASHRC_PATH"

  if grep -Fqx "$PATH_BLOCK_START" "$BASHRC_PATH"; then
    return
  fi

  {
    printf '\n%s\n' "$PATH_BLOCK_START"
    printf '# Added by codex-orchestrator installer. Uninstall keeps this block when ~/.local/bin still appears to be in use.\n'
    printf 'if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then\n'
    printf '  export PATH="$HOME/.local/bin:$PATH"\n'
    printf 'fi\n'
    printf '%s\n' "$PATH_BLOCK_END"
  } >> "$BASHRC_PATH"

  printf 'updated %s\n' "$BASHRC_PATH"
}

remove_path_block() {
  if [[ ! -f "$BASHRC_PATH" ]]; then
    return
  fi

  python - "$BASHRC_PATH" "$PATH_BLOCK_START" "$PATH_BLOCK_END" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
start = sys.argv[2]
end = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
output: list[str] = []
skipping = False
changed = False

for line in lines:
    if line == start:
        skipping = True
        changed = True
        continue
    if skipping and line == end:
        skipping = False
        continue
    if not skipping:
        output.append(line)

if changed:
    text = "\n".join(output).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
PY

  if ! grep -Fqx "$PATH_BLOCK_START" "$BASHRC_PATH"; then
    printf 'cleaned %s\n' "$BASHRC_PATH"
  fi
}

bin_dir_has_entries() {
  if [[ ! -d "$BIN_DIR" ]]; then
    return 1
  fi

  if find "$BIN_DIR" -mindepth 1 -maxdepth 1 | read -r _; then
    return 0
  fi

  return 1
}

install_wrapper() {
  mkdir -p "$BIN_DIR"

  if [[ -e "$WRAPPER_PATH" ]]; then
    current_content="$(cat "$WRAPPER_PATH")"
    if [[ "$current_content" == "$MANAGED_WRAPPER_CONTENT" ]]; then
      printf 'unchanged %s\n' "$WRAPPER_PATH"
      return
    fi

    printf 'error: %s exists and is not the managed codex-orchestrator wrapper\n' "$WRAPPER_PATH" >&2
    exit 1
  fi

  cat > "$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
exec python "\$HOME/.agents/skills/codex-orchestrator/scripts/orchestrator.py" "\$@"
EOF
  chmod 755 "$WRAPPER_PATH"
  printf 'installed %s\n' "$WRAPPER_PATH"
}

remove_wrapper() {
  if [[ ! -f "$WRAPPER_PATH" ]]; then
    return
  fi

  current_content="$(cat "$WRAPPER_PATH")"
  if [[ "$current_content" == "$MANAGED_WRAPPER_CONTENT" ]]; then
    rm "$WRAPPER_PATH"
    printf 'removed %s\n' "$WRAPPER_PATH"
  else
    printf 'skipped %s\n' "$WRAPPER_PATH"
  fi
}

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
cleanup_renamed_skill_link "orchestrator-sleep" "codex-orchestrator"

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

if [[ "$MODE" == "install" ]]; then
  install_wrapper
  ensure_path_block
else
  remove_wrapper
  if [[ ! -e "$WRAPPER_PATH" ]] && ! bin_dir_has_entries; then
    remove_path_block
  fi
fi
