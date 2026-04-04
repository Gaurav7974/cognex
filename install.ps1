Write-Host "Installing cognex..." -ForegroundColor Cyan
pip install cognex

Write-Host "Detecting AI tool config..." -ForegroundColor Cyan

$ClaudeConfig = "$env:APPDATA\Claude\claude_desktop_config.json"
$OpenCodeConfig = "$env:USERPROFILE\.config\opencode\opencode.json"
$CursorConfig = "$env:USERPROFILE\.cursor\mcp.json"

$CognexClause = '"cognex": { "command": "cognex" }'

if (Test-Path "$env:APPDATA\Claude") {
    if (Test-Path $ClaudeConfig) {
        Write-Host "Found Claude config. Add this to mcpServers in $ClaudeConfig" -ForegroundColor Yellow
        Write-Host $CognexClause
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $ClaudeConfig)
        '{"mcpServers": {"cognex": {"command": "cognex"}}}' | Out-File $ClaudeConfig
        Write-Host "Created Claude config at $ClaudeConfig" -ForegroundColor Green
    }
} elseif (Test-Path "$env:USERPROFILE\.config\opencode") {
    if (Test-Path $OpenCodeConfig) {
        Write-Host "Found OpenCode config. Add cognex to mcp section in $OpenCodeConfig" -ForegroundColor Yellow
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $OpenCodeConfig)
        @'
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cognex": {
      "type": "local",
      "command": ["cognex"],
      "enabled": true
    }
  }
}
'@ | Out-File $OpenCodeConfig
        Write-Host "Created OpenCode config at $OpenCodeConfig" -ForegroundColor Green
    }
} elseif (Test-Path "$env:USERPROFILE\.cursor") {
    if (Test-Path $CursorConfig) {
        Write-Host "Found Cursor config. Add this to mcpServers in $CursorConfig" -ForegroundColor Yellow
        Write-Host $CognexClause
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $CursorConfig)
        '{"mcpServers": {"cognex": {"command": "cognex"}}}' | Out-File $CursorConfig
        Write-Host "Created Cursor config at $CursorConfig" -ForegroundColor Green
    }
} else {
    Write-Host "No AI tool detected. Add cognex to your MCP config manually." -ForegroundColor Yellow
    Write-Host "See: https://github.com/Gaurav7974/cognex#configuration-by-cli-tool"
}

Write-Host ""
Write-Host "Done! Restart your AI tool to see 18 new cognex tools." -ForegroundColor Green
Write-Host "Docs: https://github.com/Gaurav7974/cognex"
