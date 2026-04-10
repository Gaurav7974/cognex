# Changelog

All notable changes to Cognex are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.5] - 2026-04-10

### Security
- Replaced forgeable SHA-256 truncated teleport bundle signature with Ed25519 signing
- Keys stored at .substrate/signing_key.pem, generated on first run
- Added verify_bundle() for receivers to validate incoming bundles
- Trust record injection attack prevention: rejects approval_count > 500 or violation_count > 100 on rehydration

### Performance
- Added connection pool to MemoryStore — eliminates per-call SQLite reconnect overhead
- Connections reuse WAL mode and busy_timeout settings across calls

### CLI
- Added cognex --status subcommand — shows memory count, decision count, trust records, configured AI tools, and DB path without starting the server

## [0.1.4] - 2026-04-06

### Fixed
- Timeout error: SQLite busy_timeout set to 10000ms prevents
  indefinite hangs when database is locked
- Timeout error: asyncio.wait_for wrapper on all tool calls
  converts silent 30s hangs into clear error messages
- Timeout error: SQLite write operations moved to thread pool
  executor to prevent blocking the async event loop
- Timeout error: retry logic with backoff for locked database
  writes (3 attempts, 100ms/200ms/300ms delays)
- Server startup health check added — verifies DB accessible
  before accepting MCP connections
- Concurrent access: multiple AI tools can now use Cognex
  simultaneously without deadlocking

## [0.1.3] - 2026-04-06

### Fixed
- ledger_outcome: renamed response field from "id" to
  "decision_id" to match consumer expectations
- teleport_rehydrate: 3-layer bundle deserialization handles
  dict input, JSON string of wrapper, and raw serialized string

### Performance
- memory_get_context: 47% token savings (was 11%)
- Grouped-by-type compression — all preferences on one line,
  all facts on one line, etc.
- Filler prefix stripping removes redundant words before output
- Removed wrapper overhead fields (query, search_type) saving
  ~15 tokens per call

## [0.1.2] - 2026-04-05

### Added
- 5 MCP Prompts: start-session, end-session, export-brain, what-do-you-know, daily-standup
- `cognex --install` command for auto-configuring all AI tools
- Database schema migrations (v1-v5) for seamless upgrades
- Input sanitization against prompt injection
- AGENTS.md for automatic AI tool instructions
- Hard limits on search and decay operations
- Benchmark tool for measuring token savings (~69% reduction)

### Security
- Sanitize memory content — strip control characters
- Sanitize project names — alphanumeric only
- FTS5 query sanitization to prevent injection
- Hard caps on all search results (50 max) and context (10 max)

### Changed
- Updated pyproject.toml URLs to correct GitHub repository

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
