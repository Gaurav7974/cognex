# Cognex Usage Guide

Practical commands you can copy-paste into any AI tool that has Cognex connected.
The AI will call the right tools automatically.

---

## Scenario 1 — Starting a session

Paste at the start of every coding session:

```bash
Start a new session for project "my-app".
Load all relevant memories and context.
What do we need to know before we begin?
```

---

## Scenario 2 — Ending a session

Paste when done for the day:

```bash
We are done for today. Please:
1. Save any important decisions we made
2. Save any preferences or patterns you noticed
3. End the session with a summary
```

---

## Scenario 3 — Continuing next day

Paste at the start of next session:

```bash
I am back. Project is "my-app".
Summarize what we did last time and what is left to do.
```

---

## Scenario 4 — Saving a preference

```bash
Remember that I always use type hints in Python.
```

```bash
Remember that I prefer pytest over unittest.
```

```bash
Remember that this project uses PostgreSQL not MySQL.
```

---

## Scenario 5 — Tracking a decision

```bash
We just decided to use FastAPI over Flask.
Reasons: better async support, automatic OpenAPI docs.
Please record this decision.
```

---

## Scenario 6 — Revisiting a past decision

```bash
Why did we choose FastAPI for this project?
Check if we have any past decisions about this.
```

---

## Scenario 7 — Exporting your brain

```bash
Export everything — my memories, decisions, trust records
for project "my-app" into a portable bundle.
```

Save the output JSON somewhere safe.

---

## Scenario 8 — Importing on a new machine

```bash
I have a Cognex bundle from my other machine.
Please restore everything from it.
```

Then paste the bundle JSON:

```bash
{
  "bundle_id": "...",
  "version": "1.0",
  "memory_ids": [...],
  "trust_records": [...],
  ...
}
```

---

## Scenario 9 — Sharing context with a teammate

**On your machine:**

```bash
Create a teleport bundle for project "my-app"
that my teammate can use to get up to speed.
```

**Teammate pastes on their machine:**

```bash
My teammate shared this project context bundle with me.
Please load it so I have full context on the project.
```

Then paste the bundle JSON.

---

## Scenario 10 — Trust management

```bash
From now on, always ask me before running any delete,
remove, or drop commands. Record this as a trust rule.
```

---

## Scenario 11 — Searching memory

```bash
What do you remember about my database preferences?
Search your memory for anything related to databases.
```

---

## Scenario 12 — Health check

```bash
Give me a full report on what you have stored in Cognex.
How many memories, sessions, decisions?
```

---

## Scenario 13 — Cleaning up old memories

```bash
Clean up old or irrelevant memories.
Keep only what is important.
```

---

## Scenario 14 — Multi-tool shared memory

Both Claude Code and OpenCode on the same machine share
the same Cognex database automatically. Whatever one AI
stores, the other can read.

---

## Quick reference

| You want to... | Copy-paste this |
|----------------|-----------------|
| Start session | `Start a new session for "my-project"` |
| End session | `Save context and end session` |
| Remember something | `Remember that [fact/preference]` |
| Track a decision | `Record this decision: [decision]` |
| Find past decision | `Why did we choose [X]?` |
| Export brain | `Export my Cognex bundle for "my-project"` |
| Import brain | `Load this bundle: [paste JSON]` |
| Search memory | `What do you remember about [X]?` |
| Health check | `Give me a Cognex report` |
| Clean up | `Clean up old memories` |
