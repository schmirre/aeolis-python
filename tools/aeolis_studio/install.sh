#!/usr/bin/env bash
# One-time setup of the 'aeolis-studio' command. Run once:
#   bash tools/aeolis_studio/install.sh
# After that, type 'aeolis-studio' in any new terminal to start the app.
set -e
START="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/start.sh"
chmod +x "$START"

LINE="alias aeolis-studio='bash \"$START\"'"
for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [ -f "$RC" ] || [ "$RC" = "$HOME/.bashrc" ] || continue
  touch "$RC"
  # replace an earlier line so a moved repo still works
  grep -v "alias aeolis-studio=" "$RC" > "$RC.tmp" || true
  mv "$RC.tmp" "$RC"
  printf '\n# AeoLiS Studio\n%s\n' "$LINE" >> "$RC"
done

echo "Klart. Kommandot 'aeolis-studio' finns nu i alla nya terminaler."
echo "Starta appen nu med:  bash \"$START\""
echo "eller öppna en ny terminal (+ uppe till höger i terminalpanelen) och skriv:  aeolis-studio"
