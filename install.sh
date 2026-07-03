#!/bin/sh
set -e

echo "Downloading Cognex..."
pip install cognex --upgrade --quiet

# Hand off to the Python installer for the UI and platform config
cognex-install
