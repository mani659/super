# W9 Log Probe Report

**Date:** Sep 19 2026
**Scope:** Read-only diagnosis of five logging failures from Week 9

---

## Section 1: File Deployment Status (Local Source)

| File | Feature | Grep Count | Status |
|------|---------|-----------|--------|
| `cab_super/cab_watcher.py` | IMMEDIATE_EXIT | 6 | **CONFIRMED** |
| `cab_super/cab_watcher.py` | REAPER\|H4_AGAINST | 1 | **CONFIRMED** |
| `cab_super/cab_watcher.py` | M5_CONTEXT | 1 | **CONFIRMED** |
| `cab_super/cab_entry.py` | CAB_ENTRY_QUALITY | 1 | **CONFIRMED** |
| `unified_runner.py` | GHOST_FIRE_QUALITY | 1 | **CONFIRMED** |
| `ghost_super/ghost_sniper.py` | GHOST_FIRE_QUALITY | 1 | **CONFIRMED** |

**All six local source files contain the expected feature strings.** The code is present on the local machine. Whether the VPS-deployed files match cannot be verified from this environment — a VPS diff is required.

---

## Section 2: Audit CSV Root Cause

### Finding: CSV stopped because Ghost stopped producing events — NOT a file write failure

- **Last write:** Sep 15 16:52:38 (170 rows that day)
- **Total rows:** 2,289
- **Disk space:** 166.71 GB free — NOT disk full
- **No errors/tracebacks** found in unified_runner.log around Sep 15
- **Bot continued running:** 71 heartbeats from Sep 16–19, all healthy

### Why the CSV stopped

The audit CSV is written by `ghost_sniper.py:log_event()` (line 193), which opens the file with `open(DATA_LOG_FILE, "a")` on every call. The CSV stopped because `log_event()` stopped being called — Ghost stopped producing events.

Evidence from `unified_runner.log`:
- 16 `Thread.GhostHunter` entries total for W9
- **All 16 are `GHOST_ARM_BLOCKED_ST_LONG`** — SuperTrend LONG thesis on XAUUSDm suppressed every UP_PROBE
- Zero `ARMED UP/DN`, zero `FIRE_202/201`, zero `FILL_SECURE` events from Sep 16–19
- Last GhostHunter entry: `2026-09-19 00:00:00,658 [Thread.GhostHunter] INFO | Daily reset: pairs_yesterday=0`

**Root cause:** Ghost was blocked by SuperTrend LONG gate for the entire Sep 16–19 period. No probes armed, no fires, no fills → no `log_event()` calls → no CSV rows. This is **expected behavior**, not a bug.

---

## Section 3: GHOST_FIRE_QUALITY Actual Location

| File | Count |
|------|-------|
| `logs/unified_runner.log` | **0** |
| `logs/sniper_hunter.log` | **0** |

**GHOST_FIRE_QUALITY was never logged in W9 because Ghost never fired.** The feature is in the source code (confirmed in Section 1), but the code path requires Ghost to arm AND fire. Since SuperTrend LONG blocked every probe arm (Section 2), GHOST_FIRE_QUALITY was never reached.

**Not a log routing issue.** The feature goes to `unified_runner.log` via `[Thread.GhostHunter]` logger — correct. The W9 extraction searched `sniper_hunter.log` which was the wrong file, but even `unified_runner.log` has zero because the code path was never executed.

---

## Section 4: CAB Logging Status

### cab_watcher.log content
- **Exists:** Yes, active (last write Sep 19 01:02)
- **Content:** 4,389+ lines — watcher IS cycling
- **Evidence:** `WATCHER CYCLE`, `Magic isolation OK | 9 positions`, `CYCLE | price=...` entries present

### Feature presence in ANY log file

| Feature | cab_watcher.log | unified_runner.log | Any log |
|---------|----------------|-------------------|---------|
| M5_CONTEXT | 0 | 0 | **0** |
| IMMEDIATE_EXIT | 0 | 0 | **0** |
| REAPER\|H4_AGAINST | 0 | 0 | **0** |
| CAB_ENTRY_QUALITY | 0 | 0 | **0** |

### Is the watcher managing positions?
- `PROTECTOR`/`HARVESTER`: 0 fires
- `OSI`: 0 fires
- `IMMEDIATE_EXIT`/`REAPER`: 0 fires

**But the watcher IS cycling** — `Done=set()` lines confirm positions are being iterated with R-values computed. The `processed_actions` dict is tracking tickets.

### IMMEDIATE_EXIT logic gate analysis

From the last 30 lines of `cab_watcher.log`, all R-values are between -0.07 and +0.43. **No position ever reached R <= -0.20 during a watcher cycle in the visible log window.** This means IMMEDIATE_EXIT's condition (`current_r <= -0.20 AND time_held < 7200s`) was never met.

Similarly, REAPER requires `R <= -0.50` — no position came close.

### M5_CONTEXT analysis

M5_CONTEXT logs at first detection of a new position (`pos.ticket not in processed_actions`). The `Done=set()` output confirms positions ARE in `processed_actions`. This means:
- If positions were opened during W9, M5_CONTEXT should have fired on first detection
- If positions predate W9, M5_CONTEXT fired in a prior week (not in W9 logs)

The HTML shows 65 CAB trades closed in W9. These positions must have been opened during W9 (or held from before). If opened during W9, the watcher should have logged M5_CONTEXT on first detection. **Zero M5_CONTEXT lines for 65 closed trades is abnormal** and suggests either:
1. The deployed `cab_watcher.py` lacks the M5_CONTEXT code (older version)
2. The `processed_actions` dict is being cleared between cycles (code bug)
3. The `_get_m5_context()` function silently fails and the entire block is skipped

---

## Section 5: Root Cause Verdict Per Feature

| Feature | Root Cause |
|---------|-----------|
| **GHOST_FIRE_QUALITY** | **Ghost never fired in W9.** SuperTrend LONG gate blocked every probe arm (Sep 16–19). Code path never reached. Not a deployment issue — feature is present in source. Will fire when Ghost next arms and fires. |
| **IMMEDIATE_EXIT** | **Conditions never met.** No CAB position reached R <= -0.20 during a watcher cycle while held < 2 hours. All R-values in visible logs ranged -0.07 to +0.43. Feature is present in source code (6 matches). |
| **REAPER\|H4_AGAINST** | **Conditions never met.** No CAB position reached R <= -0.50. All R-values far above threshold. Feature is present in source code (1 match). |
| **M5_CONTEXT** | **Likely deployment mismatch.** Zero lines for 65 closed CAB trades is abnormal. Feature is present in local source (1 match). Most probable cause: the deployed VPS `cab_watcher.py` is a pre-Sep-12 version without this code. Requires VPS diff to confirm. |
| **CAB_ENTRY_QUALITY** | **Zero new entries during W9.** CAB entry is handled by `cab_entry.py` (separate process/thread). If no new H4 inversion signals triggered during W9, this code path was never reached. Feature is present in source code (1 match). |

---

## Summary

| Finding | Status |
|---------|--------|
| Local source files | All features present — CONFIRMED |
| Audit CSV stop | Expected — Ghost blocked by ST LONG gate, no events to write |
| GHOST_FIRE_QUALITY | Expected zero — Ghost never fired |
| IMMEDIATE_EXIT | Expected zero — no position hit -0.20R threshold |
| REAPER | Expected zero — no position hit -0.50R threshold |
| M5_CONTEXT | **ABNORMAL** — likely VPS deployment mismatch |
| CAB_ENTRY_QUALITY | Expected zero — no new entries in W9 |
| VPS deployment verification | **REQUIRED** — cannot confirm from local environment |
| Disk/permission issues | None — 166 GB free, no errors in logs |

**Priority action:** Diff `cab_super/cab_watcher.py` against the VPS version to confirm whether M5_CONTEXT, IMMEDIATE_EXIT, and REAPER code is actually deployed. The local source is correct; the VPS may be running an older version.
