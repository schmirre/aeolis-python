#!/usr/bin/env bash
# One-time setup of the 'aeolis-studio' command. Run once:
#   bash tools/aeolis_studio/install.sh
# After that, type 'aeolis-studio' to start the app.
set -e
START="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start.sh"
chmod +x "$START"

# 1) A real command on PATH, so it works at once in the same terminal.
#    /usr/local/bin when writable (Codespaces runs as root), else ~/.local/bin.
WRAPPER='#!/usr/bin/env bash
exec bash "'"$START"'" "$@"'
INSTALLED=""
for DIR in /usr/local/bin "$HOME/.local/bin"; do
  if mkdir -p "$DIR" 2>/dev/null && [ -w "$DIR" ]; then
    printf '%s\n' "$WRAPPER" > "$DIR/aeolis-studio" && chmod +x "$DIR/aeolis-studio"
    INSTALLED="$DIR/aeolis-studio"
    break
  fi
done

# 2) Fallback alias in the shell start files (also covers a bin folder not on PATH).
LINE="alias aeolis-studio='bash \"$START\"'"
for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [ -f "$RC" ] || [ "$RC" = "$HOME/.bashrc" ] || continue
  touch "$RC"
  grep -v "alias aeolis-studio=\|^# AeoLiS Studio$" "$RC" > "$RC.tmp" || true
  mv "$RC.tmp" "$RC"
  printf '# AeoLiS Studio\n%s\n' "$LINE" >> "$RC"
done

if [ -n "$INSTALLED" ] && command -v aeolis-studio >/dev/null 2>&1; then
  echo "Klart. Skriv nu:  aeolis-studio"
else
  echo "Klart. Kör 'source ~/.bashrc' (eller öppna en ny terminal) och skriv sedan:  aeolis-studio"
fi
