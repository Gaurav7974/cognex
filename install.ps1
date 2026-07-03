Write-Host "Downloading Cognex..." -ForegroundColor Cyan
pip install cognex --upgrade --quiet

# Hand off to the Python installer for the UI and platform config
cognex-install
