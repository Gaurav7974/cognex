"""
Apply all registry.py bug fixes in one atomic pass with syntax verification.
Patterns are extracted directly from the file via inspect_registry.py output.
"""
import ast, sys
from pathlib import Path

path = Path("src/cognex_mcp/tools/registry.py")
src = path.read_text(encoding="utf-8")   # universal newlines
orig = src
log = []

def sub(old, new, tag):
    global src
    if old not in src:
        log.append(f"MISS [{tag}]  first 80: {old[:80]!r}")
        return False
    src = src.replace(old, new, 1)
    log.append(f"OK   [{tag}]")
    return True

ok = True

# ── BUG-05: audit_get_recent — project becomes optional ──────────────────
ok &= sub(
    '"project": {"type": "string", "description": "Project name to filter by"},',
    '"project": {"type": "string", "description": "Project name to filter by (empty = all projects)", "default": ""},',
    "BUG-05a",
)
ok &= sub(
    '            "required": ["project"],\n        },\n    },\n    {\n        "name": "audit_verify"',
    '            "required": [],\n        },\n    },\n    {\n        "name": "audit_verify"',
    "BUG-05b",
)

# ── BUG-06: unit_checkout — project becomes optional ─────────────────────
# Locate via the unique description string for unit_checkout
ok &= sub(
    '"description": "Get cognitive bundle (decisions, constraints, progress) for a project. Use when: preparing to work on a task or retrieving full state snapshot for a scope. Returns structured JSON for handoff.",\n        "inputSchema": {\n            "type": "object",\n            "properties": {\n                "project": {"type": "string", "description": "Project name"},',
    '"description": "Get cognitive bundle (decisions, constraints, progress) for a project. Use when: preparing to work on a task or retrieving full state snapshot for a scope. Returns structured JSON for handoff.",\n        "inputSchema": {\n            "type": "object",\n            "properties": {\n                "project": {"type": "string", "description": "Project name (empty = all projects)", "default": ""},',
    "BUG-06a",
)
ok &= sub(
    '            "required": ["project"],\n        },\n    },\n    {\n        "name": "unit_search"',
    '            "required": [],\n        },\n    },\n    {\n        "name": "unit_search"',
    "BUG-06b",
)

# ── BUG-07: recall detail enum aligned to handler values ─────────────────
ok &= sub(
    '"detail": {"type": "string", "enum": ["compact", "full"], "default": "compact"}',
    '"detail": {"type": "string", "enum": ["ids", "snippets", "full"], "default": "snippets"}',
    "BUG-07a",
)
ok &= sub(
    '"description": "Consolidated retrieval across memories, cognitive units, and decisions with compact or full detail."',
    '"description": "Consolidated retrieval across memories, cognitive units, and decisions."',
    "BUG-07b",
)
# Add query default and type the filters object
ok &= sub(
    '                "query": {"type": "string"},\n                "kind": {"type": "string", "enum": ["all", "memory", "unit", "decision"], "default": "all"},\n                "detail": {"type": "string", "enum": ["ids", "snippets", "full"], "default": "snippets"},\n                "filters": {"type": "object"},',
    '                "query": {"type": "string", "default": ""},\n                "kind": {"type": "string", "enum": ["all", "memory", "unit", "decision"], "default": "all"},\n                "detail": {"type": "string", "enum": ["ids", "snippets", "full"], "default": "snippets"},\n                "filters": {"type": "object", "properties": {"project": {"type": "string"}, "type": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}},',
    "BUG-07c",
)

# ── BUG-08: trust_query — remove non-functional mode + operation params ──
ok &= sub(
    '"description": "Consolidated trust query for checking approval posture or retrieving trust summaries.",\n        "inputSchema": {\n            "type": "object",\n            "properties": {\n                "tool_name": {"type": "string"},\n                "operation": {"type": "string"},\n                "project": {"type": "string"},\n                "mode": {"type": "string", "enum": ["check", "get", "summary"], "default": "check"},\n            },\n        },',
    '"description": "Consolidated trust query. Omit tool_name to get a full summary of all tools.",\n        "inputSchema": {\n            "type": "object",\n            "properties": {\n                "tool_name": {"type": "string", "description": "Tool to query (omit for summary)"},\n                "project": {"type": "string"},\n            },\n        },',
    "BUG-08",
)

# ── BUG-04: add required:[] normaliser at end of TOOL_DEFINITIONS ─────────
marker = (
    'TOOL_DEFINITIONS = [\n'
    '    tool for tool in TOOL_DEFINITIONS if tool["name"] not in _RETIRED_TOOL_NAMES\n'
    '] + _STATE_TOOL_DEFINITIONS\n'
)
normaliser = (
    "\n# MCP spec: every tool must explicitly declare its required fields.\n"
    "for _td in TOOL_DEFINITIONS:\n"
    '    _td["inputSchema"].setdefault("required", [])\n'
)
if marker in src:
    src = src.replace(marker, marker + normaliser, 1)
    log.append("OK   [BUG-04]")
else:
    log.append("MISS [BUG-04]  TOOL_DEFINITIONS final assignment")
    ok = False

# ── Report ────────────────────────────────────────────────────────────────
for line in log:
    print(line)

if not ok:
    print("\nABORTED: patch not written due to missing patterns above")
    sys.exit(1)

# Syntax gate
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"\nSYNTAX ERROR: {e}")
    sys.exit(1)

# Write back preserving CRLF (Windows convention for this repo)
path.write_bytes(src.replace("\n", "\r\n").encode("utf-8"))
print(f"\nDONE: {len(log)} patches applied, syntax OK")
