# Cognex Usage Guide

Practical prompts you can copy-paste into any AI tool that has Cognex connected.
The AI will call the right tools automatically.

---

## Scenario 1 — Starting a session

Paste at the start of every coding session:

> Start a new session for project [YOUR_PROJECT_NAME].
> Load all relevant memories and context.
> What do we need to know before we begin?

---

## Scenario 2 — Ending a session

Paste when done for the day:

> We are done for today. Please:
> 1. Save any important decisions we made
> 2. Save any preferences or patterns you noticed
> 3. End the session with a summary

---

## Scenario 3 — Continuing next day

Paste at the start of next session:

> I am back. Project is [YOUR_PROJECT_NAME].
> Summarize what we did last time and what is left to do.

---

## Scenario 4 — Saving a preference

> Remember that I always use type hints in Python.
> Remember that I prefer pytest over unittest.
> Remember that this project uses PostgreSQL not MySQL.

---

## Scenario 5 — Tracking a decision

> We just decided to use FastAPI over Flask.
> Reasons: better async support, automatic OpenAPI docs.
> Please record this decision.

---

## Scenario 6 — Revisiting a past decision

> Why did we choose FastAPI for this project?
> Check if we have any past decisions about this.

---

## Scenario 7 — Exporting your brain

> Export everything — my memories, decisions, trust records
> for project [YOUR_PROJECT_NAME] into a portable bundle.

Save the output JSON somewhere safe.

---

## Scenario 8 — Importing on a new machine

> I have a Cognex bundle from my other machine.
> Please restore everything from it.
> [PASTE THE BUNDLE JSON HERE]

---

## Scenario 9 — Sharing context with a teammate

> Create a teleport bundle for project [YOUR_PROJECT_NAME]
> that my teammate can use to get up to speed.

Teammate pastes on their machine:
> My teammate shared this project context bundle with me.
> Please load it so I have full context on the project.
> [PASTE BUNDLE JSON]

---

## Scenario 10 — Trust management

> From now on, always ask me before running any delete,
> remove, or drop commands. Record this as a trust rule.

---

## Scenario 11 — Searching memory

> What do you remember about my database preferences?
> Search your memory for anything related to databases.

---

## Scenario 12 — Health check

> Give me a full report on what you have stored in Cognex.
> How many memories, sessions, decisions?

---

## Scenario 13 — Cleaning up old memories

> Clean up old or irrelevant memories.
> Keep only what is important.

---

## Scenario 14 — Multi-tool shared memory

Both Claude Code and OpenCode on the same machine share
the same Cognex database automatically. Whatever one AI
stores, the other can read.

---

## Quick reference

| You want to... | Say this |
|----------------|----------|
| Start session | "Start a new session for [project]" |
| End session | "Save context and end session" |
| Remember something | "Remember that..." |
| Track a decision | "Record this decision: [decision]" |
| Find past decision | "Why did we choose [X]?" |
| Export brain | "Export my Cognex bundle" |
| Import brain | "Load this bundle: [JSON]" |
| Search memory | "What do you remember about [X]?" |
| Health check | "Give me a Cognex report" |
| Clean up | "Clean up old memories" |
