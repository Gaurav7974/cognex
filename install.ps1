Write-Host "Installing cognex..." -ForegroundColor Cyan
pip install cognex

Write-Host "Detecting AI tool configs..." -ForegroundColor Cyan

$ClaudeConfig = "$env:APPDATA\Claude\claude_desktop_config.json"
$OpenCodeConfig = "$env:USERPROFILE\.config\opencode\opencode.json"
$CursorConfig = "$env:USERPROFILE\.cursor\mcp.json"
$ClineConfig = "$env:APPDATA\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json"
$VSCodeMCP = "$env:USERPROFILE\.vscode\mcp.json"

$configured = $false

# Claude Desktop
if (Test-Path "$env:APPDATA\Claude") {
    if (-not (Test-Path $ClaudeConfig)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $ClaudeConfig) | Out-Null
        '{"mcpServers": {"cognex": {"command": "uvx", "args": ["cognex"]}}}' | Out-File $ClaudeConfig -Encoding utf8
        Write-Host "Created Claude Desktop config at $ClaudeConfig" -ForegroundColor Green
    } else {
        Write-Host "Found Claude Desktop config at $ClaudeConfig" -ForegroundColor Yellow
    }
    $configured = $true
}

# OpenCode
if (Test-Path "$env:USERPROFILE\.config\opencode") {
    if (-not (Test-Path $OpenCodeConfig)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $OpenCodeConfig) | Out-Null
        @'
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cognex": {
      "type": "local",
      "command": ["uvx", "cognex"],
      "enabled": true
    }
  }
}
'@ | Out-File $OpenCodeConfig -Encoding utf8
        Write-Host "Created OpenCode config at $OpenCodeConfig" -ForegroundColor Green
    } else {
        Write-Host "Found OpenCode config at $OpenCodeConfig" -ForegroundColor Yellow
    }
    $configured = $true
}

# Cursor
if (Test-Path "$env:USERPROFILE\.cursor") {
    if (-not (Test-Path $CursorConfig)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $CursorConfig) | Out-Null
        '{"mcpServers": {"cognex": {"command": "uvx", "args": ["cognex"]}}}' | Out-File $CursorConfig -Encoding utf8
        Write-Host "Created Cursor config at $CursorConfig" -ForegroundColor Green
    } else {
        Write-Host "Found Cursor config at $CursorConfig" -ForegroundColor Yellow
    }
    $configured = $true
}

# Cline (VS Code Extension)
if (Test-Path "$env:APPDATA\Code\User\globalStorage\saoudrizwan.claude-dev") {
    if (-not (Test-Path $ClineConfig)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $ClineConfig) | Out-Null
        @'
{
  "mcpServers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"],
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
'@ | Out-File $ClineConfig -Encoding utf8
        Write-Host "Created Cline config at $ClineConfig" -ForegroundColor Green
    } else {
        Write-Host "Found Cline config at $ClineConfig" -ForegroundColor Yellow
    }
    $configured = $true
}

# VS Code Copilot (GitHub Copilot Agent Mode)
$ProjectDir = Get-Location
$VSCodeProjectMCP = Join-Path $ProjectDir ".vscode\mcp.json"
if (Test-Path "$env:USERPROFILE\.vscode") {
    if (-not (Test-Path $VSCodeProjectMCP)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $VSCodeProjectMCP) | Out-Null
        @'
{
  "servers": {
    "cognex": {
      "command": "uvx",
      "args": ["cognex"]
    }
  }
}
'@ | Out-File $VSCodeProjectMCP -Encoding utf8
        Write-Host "Created VS Code Copilot config at $VSCodeProjectMCP" -ForegroundColor Green
    } else {
        Write-Host "Found VS Code Copilot config at $VSCodeProjectMCP" -ForegroundColor Yellow
    }
    $configured = $true
}

if (-not $configured) {
    Write-Host "No AI tool detected. Add cognex to your MCP config manually." -ForegroundColor Yellow
    Write-Host "See: https://github.com/Gaurav7974/cognex#configuration"
}

Write-Host ""
Write-Host "Done! Restart your AI tool to see 18 new cognex tools." -ForegroundColor Green
Write-Host "Docs: https://github.com/Gaurav7974/cognex"
