# Changelog

All notable changes to Cognex are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Cognitive state replication architecture across phases 2-6: explicit epistemic state on cognitive units, open questions, signed Merkle integrity roots, compact manifest handoff/resume, reconciliation conflict tracking, and low-friction `note_reasoning`.
- Provenance graph tooling for compact origin/impact traces and explicit typed links, including first-class rejected alternatives from ledger decisions.
- MCP tools for `provenance_trace`, `provenance_link`, `question_raise`, `question_resolve`, `integrity_verify`, `handoff_create`, `handoff_resume`, `reconcile_resolve`, and `note_reasoning`.

### Changed
- `unit_checkout` now includes epistemic class groupings and open questions.
- Teleport remains available as the heavyweight full-database migration path, while manifest handoff is the compact default path.
- Deprecated search/audit aliases remain callable for compatibility but are retired from the public tool registry to keep the exposed tool count capped.

### Fixed
- `CognitiveUnit` now carries the `unit_type` and epistemic fields used by stores and tools.
- Teleport bundle signing now preserves cognitive units when returning the signed copy.
- Eval harness retrieval and efficiency suites accept omitted id maps for backwards-compatible lifecycle tests.

## [0.2.0] - 2026-06-26

### Added
- Three-Tier Memory Hierarchy: consolidation of episodic memories into clusters (`memory_clusters`) and promotion to behavioral schemas (`memory_schemas`).
- Session Arc Abstraction: grouping of sessions within 7 days into session arcs (`session_arcs`) with multi-session narrative summaries.
- Peer-to-Peer Cognex Sync: content-addressed delta sync over TCP supporting `pull_and_merge` and `push` client-server replication.
- Cryptographic Handshake: Ed25519 signature verification on TCP sync server challenge messages to authenticate remote peers.
- Trust-Gated Merge & Conflict Resolution: last-writer-wins and confidence-weighted conflict resolution rules for merging memories, decisions, and cognitive units.
- Local Embedding Integration: offline vector embeddings via `sentence-transformers` and `sqlite-vec` integration.
- Reciprocal Rank Fusion (RRF): hybrid retrieval merging lexical (BM25) and semantic channels.
- Outcome-Conditioned Feedback Loops: retroactive memory relevance adjustment based on decision success/failure in ledger outcomes.
- Configurable Semaphore Backpressure: queue depth control and server-busy feedback for tool calls.
- Paginated Memory Decay: cursor-based batched decay commits to minimize SQLite locking duration.
- Explicit lifecycle initialization and dynamic imports for optional tools.

## [0.1.7] - 2026-05-03

### Added
- Concurrent sessions: multiple active sessions per CognexContext with thread-safe `_sessions` dict + `threading.Lock()`
- Audit logging: structured append-only event log with SHA256 checksums for immutability
- AuditLog class: append-only event store with `append(event_type, session_id, project, agent_id, payload)` and `get_recent(project, limit=50)` methods
- Audit verification: `verify_integrity(log_id)` method to recompute and verify entry checksums
- MCP audit tools: `audit_get_recent()` and `audit_verify()` for retrieving and verifying audit events
- Audit wiring: all 6 core MCP tools now log events (session_start, session_end, unit_commit, unit_overridden, bundle_created, bundle_rehydrated)
- Graceful audit error handling: database lock errors don't crash tool execution; logs return empty string on DB contention

### Database
- Migration 9: audit_log table with log_id, event_type, session_id, project, agent_id, payload, created_at, checksum columns
- Indices: idx_audit_log_project, idx_audit_log_created_at for efficient querying

### Changed
- DB path moved from `.substrate/cognex.db` (project cwd) to `~/.cognex.db/cognex.db` (user home directory)
- All components (engine, trust, ledger, unit_store, audit) now share centralized `~/.cognex.db/` directory

### Fixed
- Session tracking now thread-safe: concurrent sessions no longer overwrite each other
- Database lock contention: graceful error handling in audit.append() prevents tool execution failures

## [0.1.6] - 2026-04-18

### Added
- Cognitive Units: first-class structured state with content, rationale, scope, and confidence
- CognitiveUnitDelta: append-only change log per unit — full audit trail of how cognition evolved
- Delta tracking: mark_overridden() writes a delta record before decaying confidence
- Staleness scoring: computed on read from override_count, last_verified age, and confidence
- Selective retrieval: get_relevant_units() scores by BM25 + confidence + recency + scope match
- Cognitive snapshot: export_snapshot() returns full structured CHP handoff bundle with delta trail
- 8 new MCP tools: unit_commit, unit_checkout, unit_search, unit_mark_overridden, unit_verify, unit_get_relevant, unit_export_snapshot, unit_decay_stale
- TeleportBundle now carries cognitive_units for full cross-machine cognitive state transfer
- PatternAnalyzer tests added — now runs in CI
- process_transcript extractor wrapped in run_in_executor (no longer blocks event loop)
- cognex --status CLI subcommand (fix: was reported done in 0.1.5 but not working until now)

### Database
- Migration 6: cognitive_units table + cognitive_units_fts FTS5 virtual table
- Migration 7: cognitive_unit_deltas table + index

## [0.1.5] - 2026-04-10

### Security
- Replaced forgeable SHA-256 truncated teleport bundle signature with Ed25519 signing
- Keys stored at ~/.cognex.db/keys/signing_key.pem, generated on first run
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
- `cognex_start_session` returns compressed memories by default

## [0.1.0] - 2026-04-04

### Added
- 18 MCP tools across 6 categories: session, memory, trust, ledger, teleport, swarm
- Persistent SQLite storage at ~/.cognex.db.db/cognex.db
- Session management with start/end/transcript processing
- Memory add/search/context/decay with relevance scoring
- Trust engine: per-tool approval tracking with pattern learning
- Decision ledger: record decisions and outcomes for future reference
- Teleport: export and import full agent state as JSON bundle
- Swarm: compile natural language intent into multi-agent plans
- Context budget system: adaptive memory loading based on model context window
- WAL mode SQLite for safe concurrent access from multiple AI tools
- Compatible with Claude Code, OpenCode, Cursor, Codex, GitHub Copilot, Windsurf, Zed
