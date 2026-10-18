#!/usr/bin/env bash
# Starts AeoLiS Studio with one command. Usually called through the 'aeolis-studio' command
# that install.sh sets up.
#  - With conda: uses (and on first run creates) an environment called 'aeolis' with Python 3.12.
#  - Without conda: uses the current Python.
#  - Installs AeoLiS and the app's packages if they are missing.
#  - Starts the app on port 8501 (or the port given as the first argument).
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STUDIO="$REPO/tools/aeolis_studio"
PORT="${1:-8501}"

if command -v conda >/dev/null 2>&1; then
  # make 'conda activate' work inside a script
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if ! conda env list | awk '{print $1}' | grep -qx aeolis; then
    echo "Skapar Python-miljön 'aeolis' (första gången, några minuter)..."
    conda create -y -q -n aeolis python=3.12
  fi
  conda activate aeolis
fi

if ! python -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] < (3, 14) else 1)'; then
  echo "Python $(python -c 'import platform; print(platform.python_version())') stöds inte av AeoLiS (kräver 3.9-3.13)."
  exit 1
fi

if ! command -v aeolis >/dev/null 2>&1 || ! python -c 'import aeolis, streamlit, plotly, tabulate' >/dev/null 2>&1; then
  echo "Installerar AeoLiS och appen (första gången, några minuter)..."
  bash "$STUDIO/setup.sh"
fi

cd "$STUDIO"
echo "Startar AeoLiS Studio på port $PORT. Stoppa med Ctrl+C."
exec python -m streamlit run app.py --server.port "$PORT" --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection false
