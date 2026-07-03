# Cognex Usage Guide

Practical commands you can copy-paste into any AI tool that has Cognex connected.
The AI will call the right tools automatically.

---

## Scenario 1 — Starting a session arc

Paste at the start of a new week or sprint:

```bash
Start a new session arc for project "my-app".
What do we need to know before we begin this week?
```

---

## Scenario 2 — Starting a daily session

Paste at the start of every coding session:

```bash
Start a new session for project "my-app".
Load all relevant memories and context.
```

---

## Scenario 3 — Ending a session

Paste when done for the day:

```bash
We are done for today. Please:
1. Save any important decisions we made as State Units
2. Save any preferences or patterns you noticed
3. End the session with a summary
```

---

## Scenario 4 — Continuing next day

Paste at the start of next session:

```bash
I am back. Project is "my-app".
Get the context for the current session arc. Summarize what we did last time.
```

---

## Scenario 5 — Saving a preference

```bash
Remember that I always use type hints in Python.
```

```bash
Remember that I prefer pytest over unittest.
```

---

## Scenario 6 — Tracking a decision

```bash
We just decided to use FastAPI over Flask.
Reasons: better async support, automatic OpenAPI docs.
Please record this decision.
```

---

## Scenario 7 — Revisiting a past decision

```bash
Why did we choose FastAPI for this project?
Check if we have any past decisions about this.
```

---

## Scenario 8 — Syncing with another machine

**On your first machine:**
```bash
Start the cognex sync server.
(Run `python -m cognex_sync.server` in your terminal)
```

**On your second machine (or your teammate's):**
```bash
Please pull the latest cognex state from 192.168.1.100.
Merge any incoming decisions and memories.
```

---

## Scenario 9 — Exporting your state

If you can't sync over TCP, you can export a bundle:

```bash
Export everything — my state units, decisions, trust records
for project "my-app" into a portable state transfer bundle.
```

Save the output JSON somewhere safe.

---

## Scenario 10 — Importing your state

```bash
I have a Cognex state bundle from my other machine.
Please restore everything from it.
```

Then paste the bundle JSON.

---

## Scenario 11 — Trust management

```bash
From now on, always ask me before running any delete,
remove, or drop commands. Record this as a trust rule.
```

---

## Scenario 12 — Searching memory

```bash
What do you remember about my database preferences?
Search your memory for anything related to databases.
```

---

## Scenario 13 — Health check

```bash
Give me a full report on what you have stored in Cognex.
Are there any tampered audit logs?
```

---

## Scenario 14 — Cleaning up old memories

```bash
Consolidate my older episodic memories into semantic clusters.
Keep only what is important.
```

---

## Scenario 15 — Multi-tool shared memory

Both Claude Code and OpenCode on the same machine share
the same Cognex database automatically. Whatever one AI
stores, the other can read.

---

## Quick reference

| You want to... | Copy-paste this |
|----------------|-----------------|
| Start arc | `Start a new session arc for "my-project"` |
| Start session | `Start a new session for "my-project"` |
| End session | `Save context and end session` |
| Remember something | `Remember that [fact/preference]` |
| Track a decision | `Record this decision: [decision]` |
| Find past decision | `Why did we choose [X]?` |
| Sync state | `Pull the latest cognex state from [IP]` |
| Export state | `Export my state bundle for "my-project"` |
| Import state | `Load this bundle: [paste JSON]` |
| Search memory | `What do you remember about [X]?` |
| Health check | `Give me a Cognex report` |
| Clean up | `Consolidate my old memories` |
