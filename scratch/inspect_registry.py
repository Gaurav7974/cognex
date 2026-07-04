"""
Inspect and patch registry.py — handles CRLF vs LF and quote issues safely.
"""
import ast, re, sys
from pathlib import Path

path = Path("src/cognex_mcp/tools/registry.py")
src = path.read_text(encoding="utf-8")   # universal newlines → all \n

# ── Debug: print exact text around key locations ──────────────────────────
def show(label, needle):
    idx = src.find(needle)
    if idx == -1:
        print(f"[{label}] NOT FOUND: {needle[:60]!r}")
    else:
        print(f"[{label}] found at {idx}:")
        print(repr(src[idx:idx+300]))
        print()

show("unit_checkout", '"name": "unit_checkout"')
show("audit_get_recent", '"name": "audit_get_recent"')
show("trust_query", '"name": "trust_query"')
show("recall detail", '"detail":')
