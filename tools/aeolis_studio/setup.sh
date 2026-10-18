#!/usr/bin/env bash
# Installs AeoLiS (this fork) and AeoLiS Studio. Used by GitHub Codespaces and on Linux/macOS.
# The fork's pyproject lists 'ffmpeg' and 'bmi-python' (which pulls in 'docopts'); those do not
# build from pip, so AeoLiS is installed without dependencies and the ones it actually imports are added.
set -e
cd "$(dirname "$0")/../.."
# AeoLiS 3.1 supports Python 3.9-3.13
if ! python -c 'import sys; sys.exit(0 if (3, 9) <= sys.version_info[:2] < (3, 14) else 1)'; then
  echo "Python $(python -c 'import platform; print(platform.python_version())') stöds inte av AeoLiS (kräver 3.9-3.13)."
  echo "Med conda: kör 'conda create -y -n aeolis python=3.12 && conda activate aeolis' och sedan detta skript igen."
  exit 1
fi
python -m pip install --upgrade pip
python -m pip install "setuptools<80" numpy scipy netCDF4 matplotlib numba typer windrose
python -m pip install --no-deps bmi-python
python -m pip install --no-deps -e .
python -m pip install -r tools/aeolis_studio/requirements.txt
aeolis --help > /dev/null && echo "AeoLiS installerat"
