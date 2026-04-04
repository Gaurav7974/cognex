# Changelog

All notable changes to Cognex are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-04-04

### Added
- 18 MCP tools across 6 categories: session, memory, trust, ledger, teleport, swarm
- Persistent SQLite storage at ~/.cognex/cognex.db
- Session management with start/end/transcript processing
- Memory add/search/context/decay with relevance scoring
- Trust engine: per-tool approval tracking with pattern learning
- Decision ledger: record decisions and outcomes for future reference
- Teleport: export and import full agent state as JSON bundle
- Swarm: compile natural language intent into multi-agent plans
- Context budget system: adaptive memory loading based on model context window
- WAL mode SQLite for safe concurrent access from multiple AI tools
- Compatible with Claude Code, OpenCode, Cursor, Codex, GitHub Copilot, Windsurf, Zed
