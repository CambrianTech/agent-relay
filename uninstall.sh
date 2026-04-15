#!/usr/bin/env bash
#
# AIRC uninstaller
#
# Removes symlinks from ~/.claude/skills/ and ~/.local/bin/airc.
# Leaves the clone at ~/.airc-src — delete it manually to fully remove.

set -euo pipefail

CLONE_DIR="${AIRC_DIR:-$HOME/.airc-src}"
BIN_DIR="$HOME/.local/bin"
SKILLS_TARGET="$HOME/.claude/skills"

info()  { printf '  \033[1;34m->\033[0m %s\n' "$*"; }
ok()    { printf '  \033[1;32m->\033[0m %s\n' "$*"; }

# Remove skill symlinks (current names and old relay-prefixed names)
if [ -d "$CLONE_DIR/skills" ]; then
  for skill_dir in "$CLONE_DIR"/skills/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    target="$SKILLS_TARGET/$skill_name"
    if [ -L "$target" ]; then
      rm "$target"
      ok "Removed skill: $skill_name"
    fi
  done
fi
for old in "$SKILLS_TARGET"/relay-*; do
  [ -L "$old" ] && rm "$old" && ok "Removed old skill: $(basename "$old")"
done

# Remove airc binary symlink
if [ -L "$BIN_DIR/airc" ]; then
  rm "$BIN_DIR/airc"
  ok "Removed airc from PATH"
fi

echo ""
ok "Uninstalled. Clone left at $CLONE_DIR (delete manually if desired)."
