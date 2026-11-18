# VERONIKA — Next Actions (Phase 8)

**Updated:** 2026-11-18 · **Next Phase:** 8 — Coding & Automation  
**Priority:** High-impact, foundational for Phases 9+ (backend) and 13 (multi-agent)

## Action 1: Terminal Manager (Streaming + Timeouts)

**Goal:** Wrap `coding_engine.py` shell/python execution with real-time streaming UI, cancellation, timeout enforcement.

**Files to modify/create:**
- `coding_engine.py` — already has `execute_shell()` + `run_python()` (lines 83–90, 126–133); audit marks as "risky"
- `ui/terminal_panel.py` — **new** PyQt6 terminal widget (streaming output, input field)
- `ui/main_window.py` — integrate terminal panel into main layout

**Deliverables:**
1. `TerminalManager` class: wraps subprocess with:
   - Real-time stdout/stderr capture (no buffering)
   - Timeout enforcement (configurable per command)
   - Graceful SIGTERM/SIGKILL cancellation
   - Working directory + env vars support
   - Exit code + last-line error parsing
2. Terminal UI: live scrolling output, input bar, cancel button, status indicator
3. Tests: 5–8 test cases (timeout, cancel, streaming, error capture)

**Audit concern addressed:** Shell execution now has:
- Visible UI feedback (user sees command running)
- Cancellation (not hung indefinitely)
- Timeout (prevents runaway processes)

**Estimate:** 2–3 hours implementation + test

---

## Action 2: Git Manager (Status/Diff/Commit/Push with Approval)

**Goal:** Safe git operations with user approval gates, no silent commits/pushes.

**Files to create:**
- `git_manager.py` — new module in repo root or `coding/` folder
  - `get_status()` → dirty files list
  - `get_diff(paths)` → colored diff display
  - `stage(paths)` → add to index
  - `commit(message, author, amend=False)` → writes commit with approval signal
  - `pull(remote, branch)` → fetch + merge with conflict detection
  - `push(remote, branch, force=False)` → requires explicit approval

**UI integration:**
- `ui/git_panel.py` — **new** PyQt6 panel showing:
  - Current branch + upstream status
  - Dirty files (click to see diff)
  - Staging area (select → commit)
  - Commit message input
  - Approval checkbox before push/force

**Deliverables:**
1. Full-featured git wrapper (no `subprocess.run("git ...")` without safety gates)
2. Conflict detection (merge revert on conflict)
3. Tests: 6–10 test cases (status, diff, commit, push approval, conflict handling)

**Standing rule:** Owner controls git commit/push — code never auto-commits.

**Estimate:** 2–3 hours implementation + test

---

## Action 3: Self-Correction Loop (Error → Diagnose → Patch → Retry)

**Goal:** Coding agent detects runtime errors, diagnoses cause, patches code, re-tests, up to N retries.

**Files to create:**
- `self_corrector.py` — new module
  - Error parser (extracts traceback + error type)
  - Diagnostic prompt builder ("error was X at Y, likely cause is Z, try …")
  - Patch applier (file edit + re-run test)
  - Checkpoint manager (save state before retry)
  - Retry budget (max 3 attempts per task)

**Integration:**
- Hook into `coding_engine.py` task loop
- Use `TerminalManager` for test runs
- Call LLM for diagnostic prompts (reuse `ProviderManager`)

**Deliverables:**
1. Error detection + parsing
2. Diagnostic LLM prompt (context: error + code snippet + test output)
3. Patch generation + application
4. Checkpoint save/restore
5. Tests: 4–6 test cases (error detection, patch apply, retry exhaustion)

**Estimate:** 2–3 hours implementation + test

---

## Action 4: Task Orchestrator (INSPECT→RUN→VERIFY→REPORT + UI)

**Goal:** High-level task execution with progress UI, cancellation, checkpointing.

**Flow:**
1. **INSPECT** — read files, run existing tests, gather context
2. **RUN** — execute task (code edit, test, deploy, etc.)
3. **VERIFY** — validate success (test pass, file state, etc.)
4. **REPORT** — summarize results + next steps

**Files to create:**
- `task_orchestrator.py` — new module
  - `TaskOrchestrator` class with state machine
  - Event emitters for UI (progress%, current_step, status_msg)
  - Cancellation signal handling

**UI integration:**
- `ui/task_progress_panel.py` — **new** PyQt6 panel showing:
  - Current step (INSPECT/RUN/VERIFY/REPORT)
  - Progress bar + percentage
  - Live status message
  - Cancel button + confirmation

**Deliverables:**
1. State machine (INSPECT → RUN → VERIFY → REPORT → DONE/FAIL)
2. Progress event API (UI subscribes to updates)
3. Cancellation propagation (signal all running sub-tasks)
4. Checkpoint/resume (save state, resume on interrupt)
5. Tests: 3–5 test cases (workflow, cancellation, checkpoint)

**Estimate:** 2–3 hours implementation + test

---

## Action 5: Permission Levels (L1/L2/L3 Enforcement)

**Goal:** Separate approval gates for read-only, file-modify, shell+git, and dangerous ops.

**Current state:** `automation/permissions.py` exists but gaps:
- `run_shell` lacks directory check (audit H-4)
- No separation between "read file" vs "run arbitrary command"

**Levels (from SECURITY.md):**
- **L1 (Read-only)** — file read, memory search, provider status
- **L2 (File-modify)** — write/edit/create files, git operations (non-destructive)
- **L3 (Shell+Git)** — execute commands, git push, apt install
- **L4 (Dangerous)** — rm -rf, password reset, factory reset

**Files to modify:**
- `automation/permissions.py` — add level classification to every action
- `automation/approval_gate.py` — **new** approval prompt builder per level
- Tests: verify each action routed to correct level

**Deliverables:**
1. Action-to-level mapping (registry in `automation/`)
2. Approval prompt UI (differs by level: read-only = silent, L4 = strict warning)
3. Audit log entry (who approved, when, action type, result)
4. Tests: 4–6 test cases (level enforcement, approval routing)

**Estimate:** 1–2 hours implementation + test

---

## Implementation Priority (Phase 8 sequence)

| # | Action | Depends on | Est. Hours | Criticality |
|---|---|---|---|---|
| 1 | Terminal Manager | None | 2–3 | CRITICAL (unblocks others) |
| 2 | Git Manager | TerminalManager | 2–3 | HIGH (owner control, safety) |
| 3 | Permission Levels | None | 1–2 | HIGH (audit H-4 closure) |
| 4 | Self-Correction | TerminalManager + ProviderManager | 2–3 | MEDIUM (enables smart retries) |
| 5 | Task Orchestrator | All above | 2–3 | MEDIUM (UI polish) |

**Total estimate:** 10–14 hours implementation + comprehensive testing

---

## Testing strategy

Each component gets:
- 4–8 unit tests (mocked subprocesses/LLM for speed)
- 1–2 integration tests (real filesystem/git repo, cleanup after)
- Full test suite run after each action (expect 324+ baseline maintained)

Run full suite command:
```bash
pytest tests/ -v --tb=short  # expect 324 pass, 3 skip
```

---

## Known constraints

1. **No silent operations** — user always approves before destructive actions
2. **Free-first** — no paid API calls for terminal/git features
3. **Windows-first** — terminal manager must handle PowerShell + WSL paths
4. **Cancellation** — all long-running tasks must respond to SIGTERM within 2s
5. **Checkpointing** — save state before risky operations (checkout, commit, etc.)

---

## Success criteria

✅ All Phase 8 actions implemented  
✅ 324+ tests pass (no regressions from Phase 7)  
✅ Terminal streaming verified (real command output in UI)  
✅ Git operations require explicit approval before push  
✅ Self-correction loop succeeds on contrived errors (syntax, import, etc.)  
✅ Task orchestrator shows live progress + cancellation works  
✅ Permission levels enforced (audit H-4 closed)  
✅ SECURITY.md updated with new approval gates  

---

## Next session: Pick up here

1. Start with **Action 1: Terminal Manager** (unblocks everything else)
2. Run tests after each action
3. Update `DEVELOPMENT_ROADMAP.md` Phase 8 line as you go
4. Commit after each major action (e.g., "feat: terminal manager with streaming + timeouts")
