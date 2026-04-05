# Changelog

All notable changes to Cognex are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-04-05

### Performance
- FTS5 full-text search with BM25 ranking replaces basic keyword search
- 10x faster memory retrieval on large datasets
- Ranked results — most relevant memories returned first
- Auto-sync FTS index via database triggers
- SQLite WAL mode + indexes for concurrent access
- Compressed memory response format (medium/minimal/full)
- Fallback to LIKE search if FTS unavailable

### Changed
- `memory_search` now returns results ranked by relevance not recency
- `memory_get_context` now accepts `format` parameter (minimal/medium/full)
- `memory_get_context` now accepts `limit` parameter (capped at 10)
- `substrate_start_session` returns compressed memories by default

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
