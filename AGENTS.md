# Cognex Memory Layer

Cognex MCP is connected to this environment.
Use it automatically — do not wait to be asked.

## Rules

### Session lifecycle
- At the START of every session: call substrate_start_session
  with a unique session_id and the current project name
- At the END of every session: call substrate_end_session
  with a summary and list of key decisions made

### Memory management  
- When user says "remember", "don't forget", "keep in mind": 
  call memory_add immediately
- When starting work on a task: call memory_get_context
  with the task as query to load relevant context
- Never ask user to re-explain something if it can be 
  retrieved from Cognex

### Decision tracking
- When a significant technical decision is made: 
  call ledger_record with tool_used, reasoning, context
- When user asks "why did we choose X": 
  call ledger_find_similar before answering

### Trust management
- Before running destructive operations (delete, drop, rm): 
  call trust_check
- After user approves/denies an operation: call trust_record

### Cross-session continuity
- Always load context at session start
- Always save context at session end
- The user should never have to repeat themselves
