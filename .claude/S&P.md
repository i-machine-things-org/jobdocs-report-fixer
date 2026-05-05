# Standards & Practices — CodeRabbit Review Log

This file records CodeRabbit recommendations so they can be applied to future changes.
Review this file before making changes to the codebase.

---

## 2026-04-20 — `.claude/hooks/pre_commit_sp_check.py` (exception specificity + git resolution)

**Review:** CodeRabbit flagged broad `except Exception` in both `get_staged_diff` and `main`, and bare `"git"` string instead of resolved executable path.
**Result:** Fixed — using `shutil.which("git")`, `OSError`/`subprocess.SubprocessError` in `get_staged_diff`, `json.JSONDecodeError` in `main`.

### Findings

1. **Broad exception handling in hook**
   - `except Exception` swallows unexpected errors silently
   - Fix: catch `(OSError, subprocess.SubprocessError)` for subprocess calls, `json.JSONDecodeError` for stdin parse

2. **Unresolved git executable**
   - Literal `"git"` may fail if git is not on PATH in some environments
   - Fix: resolve with `shutil.which("git")`, bail early if not found

---

## 2026-04-20 — `.claude/CLAUDE.md` (no-tags fallback for version bump check)

**Review:** `git describe --tags --abbrev=0` fails on a fresh repo with no tags, breaking the version bump count command.
**Result:** Fixed — command now captures tag into `last_tag` variable with `2>/dev/null`, falls back to `git log master --oneline` when empty.

### Findings

1. **`git describe` fails on tagless repos**
   - Causes the documented version-bump shell snippet to error on fresh clones
   - Fix: wrap in a `last_tag` conditional; fall back to full log when no tag exists

---

## 2026-05-05 — `module.py` (DPAS classification not filling for all customers)

**Review:** DPAS ratings detected from delivery schedule but Classification column remained NaN for some customers (Retech).
**Result:** Fixed — two separate root causes identified and resolved.

### Findings

1. **Regex `\b` word boundaries blocked embedded DPAS strings**
   - Pattern `\bD[OX]-[A-Z]\d+\b` requires a word boundary before `D`
   - Delivery schedule column G and source report descriptions use concatenated form `DPASDX-C2INSSHIP` — `D` in `DX` is preceded by `S` (word char), so no `\b`
   - Fix: relaxed to `D[OX]-[A-Z]\d+` (no boundaries); `\d+` greedily stops at non-digits already

2. **`blank_mask` sentinel set blocked fill when source Classification was non-blank**
   - DPAS fill only ran when Classification was in `('', 'nan', 'None', '<NA>', 'NaT')`
   - Source report cells with values like `0.0` or other non-blank defaults were not in the set
   - Fix: removed `blank_mask` entirely — DPAS from delivery schedule is authoritative, fill unconditionally

<!-- Add entries here as CodeRabbit reviews land. Format:

## YYYY-MM-DD — `path/to/file.py` (short description)

**Review:** WHAT CODERABBIT FLAGGED
**Result:** outcome / resolution

### Findings

1. **Title**
   - Detail
   - Fix applied

-->
